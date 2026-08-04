"""Deploy the ClinTrace ADK agent to Vertex AI Agent Engine.

Do not set ``GOOGLE_CLOUD_PROJECT`` or ``GOOGLE_CLOUD_LOCATION`` via
``--set-env-vars``; Agent Engine reserves those names. Use
``CLINICTRACE_VERTEX_LOCATION`` if you need to override Gemini region at
runtime (instrumentation defaults 3.5 models to global).
"""

from __future__ import annotations

import asyncio
import datetime
import importlib
import inspect
import io
import json
import logging
import os
import shutil
import subprocess
import tarfile
import warnings
from typing import Any, Literal, Sequence

import click
import google.auth
import vertexai
from google.cloud import resourcemanager_v3
from google.iam.v1 import iam_policy_pb2, policy_pb2
from vertexai._genai import _agent_engines_utils
from vertexai._genai.types import AgentEngine, AgentEngineConfig, IdentityType

warnings.filterwarnings(
    "ignore", category=FutureWarning, module="google.cloud.aiplatform"
)

_LOG = logging.getLogger(__name__)

_DEPLOY_EXCLUDE_DIR_NAMES = frozenset(
    {".adk", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
)
_DEPLOY_EXCLUDE_FILE_NAMES = frozenset({".env", ".env.local"})
_PROJECT_NUMBER = "258166629293"
_DEPLOY_SERVICE_AGENT = (
    "service-%s@gcp-sa-aiplatform.iam.gserviceaccount.com" % _PROJECT_NUMBER
)
_RUNTIME_SERVICE_AGENT = (
    "service-%s@gcp-sa-aiplatform-re.iam.gserviceaccount.com" % _PROJECT_NUMBER
)
_IAM_ROLES_TO_VERIFY = {
    _DEPLOY_SERVICE_AGENT: frozenset({"roles/secretmanager.secretAccessor"}),
    _RUNTIME_SERVICE_AGENT: frozenset(
        {
            "roles/aiplatform.user",
            "roles/secretmanager.secretAccessor",
        }
    ),
}

_AGENT_ENGINE_REQUIRED_PACKAGES = (
    "google-adk",
    "google-cloud-aiplatform",
    "arize-phoenix-otel",
    "arize-phoenix-client",
    "openinference-instrumentation-google-adk",
    "python-dotenv",
)


def _read_requirements_lines(requirements_file: str) -> list[str]:
    """Return non-empty, non-comment lines from a requirements file."""
    with open(requirements_file, encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.strip().startswith("#")
        ]


def _default_staging_bucket(project: str) -> str:
    """Return the project Agent Engine staging bucket URI."""
    return "gs://%s-agent-engine-staging" % project


def _should_exclude_deploy_path(rel_path: str) -> bool:
    """Return True when a relative path must be omitted from deploy tarballs."""
    parts = rel_path.split(os.sep)
    if parts[-1] in _DEPLOY_EXCLUDE_FILE_NAMES:
        return True
    if parts[-1].endswith(".pyc"):
        return True
    return any(part in _DEPLOY_EXCLUDE_DIR_NAMES for part in parts)


def _copytree_filtered(src: str, dst: str) -> None:
    """Copy a package tree while excluding local-only artifacts."""
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        dirs[:] = [
            name
            for name in dirs
            if not _should_exclude_deploy_path(
                os.path.join(rel_root, name) if rel_root != "." else name
            )
        ]
        for filename in files:
            rel_path = (
                os.path.join(rel_root, filename) if rel_root != "." else filename
            )
            if _should_exclude_deploy_path(rel_path):
                continue
            src_path = os.path.join(root, filename)
            dst_path = os.path.join(dst, rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)


def _prune_package_for_deploy(package_dir: str, backup_root: str) -> None:
    """Move excluded paths out of the package tree before source-file deploy."""
    if os.path.isdir(backup_root):
        shutil.rmtree(backup_root, ignore_errors=True)
    os.makedirs(backup_root, exist_ok=True)
    paths_to_move: list[str] = []
    for root, dirs, files in os.walk(package_dir):
        rel_root = os.path.relpath(root, package_dir)
        kept_dirs: list[str] = []
        for dirname in dirs:
            rel_path = (
                os.path.join(rel_root, dirname) if rel_root != "." else dirname
            )
            if _should_exclude_deploy_path(rel_path):
                paths_to_move.append(os.path.join(root, dirname))
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs
        for filename in files:
            rel_path = (
                os.path.join(rel_root, filename) if rel_root != "." else filename
            )
            if _should_exclude_deploy_path(rel_path):
                paths_to_move.append(os.path.join(root, filename))
    paths_to_move.sort(key=lambda path: path.count(os.sep), reverse=True)
    for src in paths_to_move:
        rel_path = os.path.relpath(src, package_dir)
        dst = os.path.join(backup_root, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
    _LOG.info(
        "Pruned excluded paths from %s into %s",
        package_dir,
        backup_root,
    )


def _restore_pruned_package(package_dir: str, backup_root: str) -> None:
    """Restore pruned paths after deploy completes."""
    if not os.path.isdir(backup_root):
        return
    for name in os.listdir(backup_root):
        src = os.path.join(backup_root, name)
        dst = os.path.join(package_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    shutil.rmtree(backup_root, ignore_errors=True)
    _LOG.info("Restored pruned paths to %s", package_dir)


def _normalize_source_package_path(package_path: str) -> str:
    """Return a project-relative package path without a leading ``./`` prefix."""
    real_path = os.path.realpath(package_path)
    project_dir = os.path.realpath(os.getcwd())
    if real_path.startswith(project_dir + os.sep):
        return os.path.relpath(real_path, project_dir)
    return package_path.lstrip("./")


def _list_source_tarball_members(source_packages: Sequence[str]) -> list[str]:
    """Return member paths in the inline tarball the Vertex SDK builds."""
    tar_fileobj = io.BytesIO()
    with tarfile.open(fileobj=tar_fileobj, mode="w|gz") as tar:
        for package in source_packages:
            tar.add(package)
    tar_fileobj.seek(0)
    with tarfile.open(fileobj=tar_fileobj, mode="r:gz") as tar:
        return sorted(member.name for member in tar.getmembers())


def _entrypoint_module_to_tar_path(entrypoint_module: str) -> str:
    """Map a Python module path to the expected tarball member path."""
    return "%s.py" % entrypoint_module.replace(".", os.sep)


def _validate_source_tarball_layout(
    *,
    source_packages: Sequence[str],
    entrypoint_module: str,
) -> list[str]:
    """Log tarball layout and fail fast when the entrypoint path is missing."""
    members = _list_source_tarball_members(source_packages)
    expected_path = _entrypoint_module_to_tar_path(entrypoint_module)
    package_names = [
        os.path.basename(path.rstrip(os.sep)) for path in source_packages
    ]
    nested_prefixes = ["%s/" % name for name in package_names]
    is_nested = any(
        member.startswith(prefix) for member in members for prefix in nested_prefixes
    )
    is_flat = expected_path in members and not is_nested

    click.echo("\n📦 Source tarball layout (matches Vertex inline archive):")
    click.echo("  Packages: %s" % ", ".join(source_packages))
    if is_nested:
        click.echo("  Layout: nested (e.g. clintrace_agent/agent_engine_app.py)")
    elif is_flat:
        click.echo("  Layout: flat (e.g. agent_engine_app.py at archive root)")
    else:
        click.echo("  Layout: unrecognized")
    click.echo("  Member count: %d" % len(members))
    for member in members[:20]:
        click.echo("    %s" % member)
    if len(members) > 20:
        click.echo("    ... (%d more)" % (len(members) - 20))

    init_paths = ["%s/__init__.py" % name for name in package_names]
    for init_path in init_paths:
        if init_path in members:
            click.echo("  Package marker: %s present" % init_path)
        elif is_nested:
            click.echo(
                "  ⚠️  Missing %s — nested imports will fail on the runtime."
                % init_path
            )

    if expected_path in members:
        click.echo("  Entrypoint file: %s ✓" % expected_path)
    else:
        flat_module = entrypoint_module.split(".")[-1]
        flat_path = "%s.py" % flat_module
        hint = ""
        if is_nested and flat_path in members:
            hint = " Try --entrypoint-module=%s." % flat_module
        elif is_flat:
            nested_guess = "%s.%s" % (package_names[0], flat_module)
            hint = " Try --entrypoint-module=%s." % nested_guess
        raise click.ClickException(
            "Entrypoint module '%s' not found in tarball (expected %s).%s"
            % (entrypoint_module, expected_path, hint)
        )

    if entrypoint_module.startswith("agent."):
        click.echo(
            "  Warning: entrypoint uses legacy 'agent.' prefix; prefer "
            "'clintrace_agent.' to avoid platform namespace collisions."
        )
    return members


def _remove_transient_artifacts(package_dir: str) -> None:
    """Drop bytecode trees recreated during local import before SDK tar upload."""
    for root, dirs, files in os.walk(package_dir, topdown=False):
        for dirname in dirs:
            if dirname == "__pycache__":
                shutil.rmtree(os.path.join(root, dirname), ignore_errors=True)
        for filename in files:
            if filename.endswith(".pyc"):
                os.remove(os.path.join(root, filename))


def _stage_source_packages(source_packages: Sequence[str]) -> tuple[str, str | None]:
    """Prune excluded artifacts and return the package dir for source deploy."""
    if len(source_packages) != 1:
        raise ValueError(
            "Filtered staging supports exactly one source package directory."
        )
    source_root = os.path.realpath(source_packages[0])
    backup_root = os.path.join(os.getcwd(), ".deploy_staging", "backup")
    _prune_package_for_deploy(source_root, backup_root)
    return source_root, backup_root


def _resolve_requirements_path(requirements_file: str) -> str:
    """Return an absolute path to the requirements file."""
    if os.path.isabs(requirements_file):
        return os.path.realpath(requirements_file)
    return os.path.realpath(os.path.join(os.getcwd(), requirements_file))


def _resolve_source_requirements_api_path(
    source_package_dir: str,
    requirements_file: str,
) -> str:
    """Return the requirements path expected by the source-file deploy API."""
    local_path = _resolve_requirements_path(requirements_file)
    package_dir = os.path.realpath(source_package_dir)
    package_name = os.path.basename(package_dir.rstrip(os.sep))
    if local_path.startswith(package_dir + os.sep):
        rel_inside_pkg = os.path.relpath(local_path, package_dir)
        return "%s/%s" % (package_name, rel_inside_pkg)
    return requirements_file


def verify_deploy_iam(project: str) -> None:
    """Log IAM coverage for Agent Platform deploy and runtime service agents."""
    click.echo("\n🔐 Verifying Agent Platform service agent IAM...")
    try:
        result = subprocess.run(
            [
                "gcloud",
                "projects",
                "get-iam-policy",
                project,
                "--format=json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        policy = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        click.echo("  ⚠️  Could not read project IAM policy: %s" % exc)
        return

    role_members: dict[str, set[str]] = {}
    for binding in policy.get("bindings", []):
        role = binding.get("role", "")
        role_members.setdefault(role, set()).update(binding.get("members", []))

    for service_account, required_roles in _IAM_ROLES_TO_VERIFY.items():
        member = "serviceAccount:%s" % service_account
        click.echo("  %s" % service_account)
        for role in sorted(required_roles):
            if member in role_members.get(role, set()):
                click.echo("    ✅ %s" % role)
            else:
                click.echo("    ❌ missing %s" % role)


def verify_deployed_agent(remote_agent: Any) -> None:
    """Print operation schemas and probe session creation on the live agent."""
    click.echo("\n🧪 Verifying deployed agent...")
    try:
        schemas = remote_agent.operation_schemas()
        click.echo("  operation_schemas: %d operations" % len(schemas))
        for schema in schemas[:8]:
            name = schema.get("name", schema) if isinstance(schema, dict) else schema
            click.echo("    - %s" % name)
        if len(schemas) > 8:
            click.echo("    ... and %d more" % (len(schemas) - 8))
    except Exception as exc:
        click.echo("  ⚠️  operation_schemas failed: %s" % exc)

    async def _probe() -> None:
        session = await remote_agent.async_create_session(user_id="deploy_verify")
        click.echo("  ✅ async_create_session ok (id=%s)" % session.get("id"))

    try:
        asyncio.run(_probe())
    except Exception as exc:
        click.echo("  ❌ async_create_session failed: %s" % exc)


def validate_agent_engine_requirements(requirements_file: str) -> None:
    """Fail fast when deploy requirements omit critical runtime packages."""
    if not os.path.exists(requirements_file):
        raise FileNotFoundError(
            "Requirements file not found: %s" % requirements_file
        )
    lines = _read_requirements_lines(requirements_file)
    if not lines:
        raise ValueError(
            "Requirements file is empty: %s" % requirements_file
        )
    normalized = [
        line.split("[", 1)[0].split("==")[0].split(">=")[0].split("<=")[0].strip()
        for line in lines
    ]
    missing = [
        pkg
        for pkg in _AGENT_ENGINE_REQUIRED_PACKAGES
        if not any(name == pkg or name.startswith(pkg + "-") for name in normalized)
    ]
    if missing:
        raise ValueError(
            "Requirements file %s is missing Agent Engine packages: %s"
            % (requirements_file, ", ".join(missing))
        )


def generate_class_methods_from_agent(agent_instance: Any) -> list[dict[str, Any]]:
    """Build class_methods from the agent's ``register_operations()``."""
    registered_operations = _agent_engines_utils._get_registered_operations(
        agent=agent_instance
    )
    class_methods_spec = _agent_engines_utils._generate_class_methods_spec_or_raise(
        agent=agent_instance,
        operations=registered_operations,
    )
    return [
        _agent_engines_utils._to_dict(method_spec)
        for method_spec in class_methods_spec
    ]


_RESERVED_AGENT_ENGINE_ENV_VARS = frozenset(
    {
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_CLOUD_QUOTA_PROJECT",
        "PORT",
        "K_SERVICE",
        "K_REVISION",
        "K_CONFIGURATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
    }
)


def _sanitize_deploy_env_vars(env_vars: dict[str, Any]) -> dict[str, Any]:
    """Drop reserved Agent Engine env vars that break instance registration."""
    sanitized = dict(env_vars)
    for key in _RESERVED_AGENT_ENGINE_ENV_VARS:
        if key in sanitized:
            _LOG.warning(
                "Removing reserved Agent Engine env var %s=%s "
                "(platform injects this; use CLINICTRACE_VERTEX_LOCATION "
                "for Gemini region overrides).",
                key,
                sanitized.pop(key),
            )
    return sanitized


def parse_key_value_pairs(kv_string: str | None) -> dict[str, str]:
    """Parse comma-separated KEY=VALUE pairs."""
    result: dict[str, str] = {}
    if not kv_string:
        return result
    for pair in kv_string.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            result[key.strip()] = value.strip()
        else:
            _LOG.warning("Skipping malformed key-value pair: %s", pair)
    return result


def parse_secrets(secrets_string: str | None) -> dict[str, dict[str, str]]:
    """Parse ENV_VAR=SECRET_ID or ENV_VAR=SECRET_ID:VERSION."""
    raw = parse_key_value_pairs(secrets_string)
    result: dict[str, dict[str, str]] = {}
    for key, spec in raw.items():
        if ":" not in spec:
            secret_id, version = spec, "latest"
        else:
            secret_id, _, version = spec.rpartition(":")
        result[key] = {"secret": secret_id.strip(), "version": version.strip()}
    return result


def _secret_binding(secret_id_or_with_version: str) -> dict[str, str]:
    """Return ``{secret, version}`` for Agent Engine secret_env."""
    spec = secret_id_or_with_version.strip()
    if not spec:
        return {"secret": "", "version": "latest"}
    if ":" in spec:
        sid, _, ver = spec.rpartition(":")
        return {"secret": sid.strip(), "version": ver.strip() or "latest"}
    return {"secret": spec, "version": "latest"}


def format_env_value(value: Any) -> str:
    """Format an env value for logs (mask secrets)."""
    if isinstance(value, dict) and "secret" in value and "version" in value:
        return "[secret:%s:%s]" % (value["secret"], value["version"])
    return str(value)


def write_deployment_metadata(
    remote_agent: Any,
    *,
    project: str,
    location: str,
    display_name: str,
    metadata_file: str = "deployment_metadata.json",
) -> None:
    """Write deployment metadata for Agent Engine."""
    metadata = {
        "remote_agent_engine_id": remote_agent.api_resource.name,
        "deployment_target": "agent_engine",
        "is_a2a": False,
        "deployment_timestamp": datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat(),
        "project": project,
        "location": location,
        "display_name": display_name,
    }
    with open(metadata_file, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    _LOG.info("Agent Engine ID written to %s", metadata_file)


def print_deployment_success(
    remote_agent: Any,
    location: str,
    project: str,
) -> None:
    """Print success line and console playground URL."""
    resource_name_parts = remote_agent.api_resource.name.split("/")
    agent_engine_id = resource_name_parts[-1]
    project_number = resource_name_parts[1]
    print("\n✅ Deployment successful!")
    service_account = remote_agent.api_resource.spec.service_account
    if service_account:
        print("Service Account: %s" % service_account)
    else:
        default_sa = (
            "service-%s@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
            % project_number
        )
        print("Service Account: %s" % default_sa)
    playground_url = (
        "https://console.cloud.google.com/vertex-ai/agents/agent-engines/"
        "locations/%s/agent-engines/%s/playground?project=%s"
        % (location, agent_engine_id, project)
    )
    print("\n📊 Open Console Playground: %s\n" % playground_url)
    print("Set in .env:")
    print("  AGENT_ENGINE_RESOURCE_ID=%s" % remote_agent.api_resource.name)


def setup_agent_identity(client: Any, project: str, display_name: str) -> Any:
    """Create agent with identity and grant required IAM roles."""
    click.echo("\n🔧 Creating agent identity for: %s" % display_name)
    agent = client.agent_engines.create(
        config={
            "identity_type": IdentityType.AGENT_IDENTITY,
            "display_name": display_name,
        }
    )
    roles = [
        "roles/aiplatform.user",
        "roles/serviceusage.serviceUsageConsumer",
        "roles/browser",
        "roles/cloudapiregistry.viewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
    ]
    principal = "principal://%s" % agent.api_resource.spec.effective_identity
    click.echo("🔐 Granting IAM roles to: %s" % principal)
    proj_client = resourcemanager_v3.ProjectsClient()
    policy = proj_client.get_iam_policy(
        request=iam_policy_pb2.GetIamPolicyRequest(resource="projects/%s" % project)
    )
    for role in roles:
        policy.bindings.append(policy_pb2.Binding(role=role, members=[principal]))
    proj_client.set_iam_policy(
        request=iam_policy_pb2.SetIamPolicyRequest(
            resource="projects/%s" % project, policy=policy
        )
    )
    click.echo("  ✅ Agent identity ready")
    return agent


@click.command()
@click.option("--project", default=None, help="GCP project ID (ADC default)")
@click.option("--location", default="us-central1", help="Agent Engine region")
@click.option(
    "--display-name",
    default="ClinTrace Triage Agent",
    help="Display name for the Agent Engine resource",
)
@click.option(
    "--description",
    default=(
        "Clinical triage pipeline with traceable reasoning and Phoenix feedback"
    ),
    help="Description stored on the Agent Engine resource",
)
@click.option(
    "--deploy-mode",
    type=click.Choice(["source", "pickle"], case_sensitive=False),
    default="source",
    help="source=ADK/doc inline tarball; pickle=agent object + package_spec",
)
@click.option(
    "--source-packages",
    multiple=True,
    default=["clintrace_agent"],
    help="Agent source package dir (filtered copy excludes .env/.adk/pycache)",
)
@click.option(
    "--entrypoint-module",
    default="clintrace_agent.agent_engine_app",
    help="Python module for the AdkApp entrypoint",
)
@click.option(
    "--entrypoint-object",
    default="agent_engine",
    help="Module-level variable holding the AdkApp instance",
)
@click.option(
    "--requirements-file",
    default="clintrace_agent/requirements.txt",
    help="Path to requirements.txt uploaded into spec.package_spec",
)
@click.option(
    "--staging-bucket",
    default=None,
    help="GCS staging bucket (gs://...) for pickle + dependencies upload",
)
@click.option(
    "--python-version",
    default=None,
    help="Python runtime version (default: current interpreter major.minor)",
)
@click.option(
    "--set-env-vars",
    default=None,
    help="Comma-separated KEY=VALUE (non-secret config)",
)
@click.option(
    "--set-secrets",
    default=None,
    help="ENV_VAR=SECRET_ID or ENV_VAR=SECRET_ID:VERSION",
)
@click.option(
    "--phoenix-api-key-secret",
    envvar="PHOENIX_API_KEY_SECRET_ID",
    default="clinictrace-phoenix-api-key",
    help="Secret Manager id for PHOENIX_API_KEY",
)
@click.option(
    "--phoenix-mcp-service-key-secret",
    envvar="PHOENIX_MCP_SERVICE_KEY_SECRET_ID",
    default="clinictrace-mcp-service-api-key",
    help="Secret Manager id for PHOENIX_MCP_SERVICE_KEY",
)
@click.option("--labels", default=None, help="Comma-separated labels KEY=VALUE")
@click.option("--service-account", default=None, help="Custom runtime SA email")
@click.option("--min-instances", type=int, default=1)
@click.option("--max-instances", type=int, default=10)
@click.option("--cpu", default="2")
@click.option("--memory", default="4Gi")
@click.option("--container-concurrency", type=int, default=5)
@click.option("--num-workers", type=int, default=1)
@click.option("--agent-identity", is_flag=True, default=False)
@click.option("--skip-verify", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
def deploy_agent_engine_app(
    project: str | None,
    location: str,
    display_name: str,
    description: str,
    deploy_mode: Literal["source", "pickle"],
    source_packages: tuple[str, ...],
    entrypoint_module: str,
    entrypoint_object: str,
    requirements_file: str,
    staging_bucket: str | None,
    python_version: str | None,
    set_env_vars: str | None,
    set_secrets: str | None,
    phoenix_api_key_secret: str | None,
    phoenix_mcp_service_key_secret: str | None,
    labels: str | None,
    service_account: str | None,
    min_instances: int,
    max_instances: int,
    cpu: str,
    memory: str,
    container_concurrency: int,
    num_workers: int,
    agent_identity: bool,
    skip_verify: bool,
    dry_run: bool,
) -> AgentEngine | None:
    """Deploy or update ClinTrace on Vertex AI Agent Engine."""
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    env_vars: dict[str, Any] = parse_key_value_pairs(set_env_vars)
    secrets = parse_secrets(set_secrets)

    if phoenix_api_key_secret and "PHOENIX_API_KEY" not in secrets:
        secrets["PHOENIX_API_KEY"] = _secret_binding(phoenix_api_key_secret)
    if phoenix_mcp_service_key_secret and "PHOENIX_MCP_SERVICE_KEY" not in secrets:
        secrets["PHOENIX_MCP_SERVICE_KEY"] = _secret_binding(
            phoenix_mcp_service_key_secret
        )

    env_vars.update(secrets)
    env_vars = _sanitize_deploy_env_vars(env_vars)
    env_vars["GOOGLE_CLOUD_REGION"] = location
    env_vars["NUM_WORKERS"] = str(num_workers)
    env_vars.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")
    env_vars.setdefault(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false"
    )
    env_vars.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

    if not project:
        _, project = google.auth.default()

    print(
        """
    ╔═══════════════════════════════════════════════════════════╗
    ║   ClinTrace Triage Agent → Vertex AI Agent Engine         ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    )

    click.echo("\n📋 Deployment parameters:")
    for name, value in (
        ("Project", project),
        ("Location", location),
        ("Display name", display_name),
        ("Min instances", min_instances),
        ("Max instances", max_instances),
        ("CPU", cpu),
        ("Memory", memory),
        ("Concurrency", container_concurrency),
    ):
        click.echo("  %s: %s" % (name, value))
    if service_account:
        click.echo("  Service account: %s" % service_account)
    if agent_identity:
        click.echo("  Agent identity: enabled (preview)")
    if env_vars:
        click.echo("\n🌍 Resolved environment (secrets masked):")
        for key in sorted(env_vars.keys()):
            click.echo("  %s: %s" % (key, format_env_value(env_vars[key])))

    verify_deploy_iam(project)

    source_packages_list = list(source_packages)
    prune_backup_root: str | None = None
    try:
        staged_package, prune_backup_root = _stage_source_packages(
            source_packages_list
        )
        deploy_source_packages = [_normalize_source_package_path(staged_package)]
    except ValueError:
        deploy_source_packages = [
            _normalize_source_package_path(path) for path in source_packages_list
        ]
        staged_package = os.path.realpath(source_packages_list[0])

    if deploy_mode == "source":
        _validate_source_tarball_layout(
            source_packages=deploy_source_packages,
            entrypoint_module=entrypoint_module,
        )

    http_options = {"api_version": "v1beta1"} if agent_identity else None
    client = vertexai.Client(
        project=project,
        location=location,
        http_options=http_options,
    )
    vertexai.init(project=project, location=location)

    _LOG.info("Importing %s (object %s)", entrypoint_module, entrypoint_object)
    module = importlib.import_module(entrypoint_module)
    agent_instance = getattr(module, entrypoint_object)
    if inspect.iscoroutine(agent_instance):
        _LOG.info("Awaiting coroutine %s...", entrypoint_object)
        agent_instance = asyncio.run(agent_instance)
    class_methods_list = generate_class_methods_from_agent(agent_instance)
    labels_dict = parse_key_value_pairs(labels)
    req_local_path = _resolve_requirements_path(requirements_file)
    requirements = _read_requirements_lines(req_local_path)
    resolved_staging_bucket = staging_bucket or _default_staging_bucket(project)
    resolved_python_version = python_version or "3.11"
    req_api_path = _resolve_source_requirements_api_path(
        staged_package,
        requirements_file,
    )

    validate_agent_engine_requirements(req_local_path)
    _LOG.info("Requirements file: %s (%d lines)", req_local_path, len(requirements))
    _LOG.info("Requirements API path: %s", req_api_path)
    _LOG.info("Python version: %s", resolved_python_version)
    click.echo("  Deploy mode: %s" % deploy_mode)
    click.echo("  Python version: %s" % resolved_python_version)
    click.echo("  Requirements API path: %s" % req_api_path)

    if deploy_mode == "source":
        click.echo("  Entrypoint module: %s" % entrypoint_module)
        config = AgentEngineConfig(
            display_name=display_name,
            description=description,
            source_packages=deploy_source_packages,
            entrypoint_module=entrypoint_module,
            entrypoint_object=entrypoint_object,
            class_methods=class_methods_list,
            requirements_file=req_api_path,
            env_vars=env_vars,
            service_account=service_account,
            labels=labels_dict,
            min_instances=min_instances,
            max_instances=max_instances,
            resource_limits={"cpu": cpu, "memory": memory},
            container_concurrency=container_concurrency,
            agent_framework="google-adk",
            python_version=resolved_python_version,
            identity_type=IdentityType.AGENT_IDENTITY if agent_identity else None,
        )
    else:
        click.echo("  Staging bucket: %s" % resolved_staging_bucket)
        config = AgentEngineConfig(
            display_name=display_name,
            description=description,
            staging_bucket=resolved_staging_bucket,
            requirements=requirements,
            extra_packages=deploy_source_packages,
            class_methods=class_methods_list,
            env_vars=env_vars,
            service_account=service_account,
            labels=labels_dict,
            min_instances=min_instances,
            max_instances=max_instances,
            resource_limits={"cpu": cpu, "memory": memory},
            container_concurrency=container_concurrency,
            agent_framework="google-adk",
            python_version=resolved_python_version,
            identity_type=IdentityType.AGENT_IDENTITY if agent_identity else None,
        )

    if dry_run:
        if prune_backup_root:
            _restore_pruned_package(staged_package, prune_backup_root)
        click.echo("\nDry run: skipping Agent Engine list/create/update.")
        return None

    existing_agents = list(client.agent_engines.list())
    matching_agents = [
        a for a in existing_agents if a.api_resource.display_name == display_name
    ]

    if agent_identity and not matching_agents:
        matching_agents = [setup_agent_identity(client, project, display_name)]

    action = "Updating" if matching_agents else "Creating"
    click.echo("\n🚀 %s agent: %s ..." % (action, display_name))

    try:
        if deploy_mode == "source":
            _remove_transient_artifacts(staged_package)
            if matching_agents:
                remote_agent = client.agent_engines.update(
                    name=matching_agents[0].api_resource.name,
                    config=config,
                )
            else:
                remote_agent = client.agent_engines.create(config=config)
        elif matching_agents:
            remote_agent = client.agent_engines.update(
                name=matching_agents[0].api_resource.name,
                agent=agent_instance,
                config=config,
            )
        else:
            remote_agent = client.agent_engines.create(
                agent=agent_instance,
                config=config,
            )
    finally:
        if prune_backup_root:
            _restore_pruned_package(staged_package, prune_backup_root)

    if set_secrets is not None and not secrets and matching_agents:
        clear_op = client.agent_engines._update(
            name=remote_agent.api_resource.name,
            config={
                "spec": {"deployment_spec": {"secret_env": []}},
                "update_mask": "spec.deployment_spec.secret_env",
            },
        )
        _agent_engines_utils._await_operation(
            operation_name=clear_op.name,
            get_operation_fn=client.agent_engines._get_agent_operation,
        )

    write_deployment_metadata(
        remote_agent, project=project, location=location, display_name=display_name
    )
    print_deployment_success(remote_agent, location, project)
    if not skip_verify:
        click.echo("\n⏳ Waiting 120s for instances to become ready...")
        import time

        time.sleep(120)
        verify_deployed_agent(remote_agent)
    return remote_agent


if __name__ == "__main__":
    deploy_agent_engine_app()
