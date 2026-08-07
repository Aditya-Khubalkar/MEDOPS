/**
 * MEDOPS — Tile Provider Abstraction
 * ====================================
 * Centralizes all tile/routing/geocoding provider configurations.
 *
 * SERVICE TRANSPARENCY:
 * ─────────────────────
 * - OpenStreetMap (OSM) tiles: Open Data, free for dev/demo.
 *   Subject to OSM Usage Policy: https://operations.osmfoundation.org/policies/tiles/
 *   Do NOT use at high volume without a self-hosted/commercial tile server.
 *
 * - OSRM (Open Source Routing Machine): Open source, free demo server.
 *   Demo server at router.project-osrm.org is for TESTING ONLY.
 *   Not for production use. Self-host for production.
 *
 * - Nominatim: OSM geocoding. Free for low-volume, attribution required.
 *   https://operations.osmfoundation.org/policies/nominatim/
 *
 * - CartoDB Basemaps (Voyager/Positron/DarkMatter): Free for demo/low-volume.
 *   Attribution required. Check CARTO usage policy for commercial use.
 */

// ──────────────────────────────────────────────────
// TILE PROVIDERS
// ──────────────────────────────────────────────────

export const TILE_PROVIDERS = {
  /**
   * OpenStreetMap Standard
   * Free, open data. Attribution required.
   * Not for heavy production use without self-hosting.
   */
  OSM_STANDARD: {
    id: 'osm_standard',
    name: 'OpenStreetMap Standard',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    maxZoom: 19,
    isOpenSource: true,
    isFreeForDemo: true,
    note: 'Subject to OSM tile usage policy. Self-host for production.',
  },

  /**
   * CartoDB Positron (light theme) — matches MEDOPS light mode
   * Free for demo, attribution required.
   */
  CARTO_POSITRON: {
    id: 'carto_positron',
    name: 'CartoDB Positron',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>',
    maxZoom: 20,
    isOpenSource: false,
    isFreeForDemo: true,
    note: 'Free for low-volume/demo. Check CARTO policy for commercial use.',
  },

  /**
   * CartoDB Dark Matter — matches MEDOPS dark mode
   */
  CARTO_DARK: {
    id: 'carto_dark',
    name: 'CartoDB Dark Matter',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>',
    maxZoom: 20,
    isOpenSource: false,
    isFreeForDemo: true,
    note: 'Free for low-volume/demo. Check CARTO policy for commercial use.',
  },
};

// Default tile providers for light/dark themes
export const DEFAULT_LIGHT_TILE = TILE_PROVIDERS.CARTO_POSITRON;
export const DEFAULT_DARK_TILE = TILE_PROVIDERS.CARTO_DARK;

// ──────────────────────────────────────────────────
// ROUTING PROVIDERS
// ──────────────────────────────────────────────────

export const ROUTING_PROVIDERS = {
  /**
   * OSRM Demo Server (Open Source Routing Machine)
   * Open source. Demo server is for TESTING ONLY.
   * Self-host OSRM for production: https://project-osrm.org/
   */
  OSRM_DEMO: {
    id: 'osrm_demo',
    name: 'OSRM Demo Server',
    baseUrl: 'https://router.project-osrm.org/route/v1/driving',
    isOpenSource: true,
    isFreeForDemo: true,
    note: 'Demo server — NOT for production. Self-host OSRM for production use.',
    rateLimit: 'Unofficial. Do not spam. Max ~1 req/sec for testing.',
  },
};

export const DEFAULT_ROUTING_PROVIDER = ROUTING_PROVIDERS.OSRM_DEMO;

// ──────────────────────────────────────────────────
// GEOCODING PROVIDERS
// ──────────────────────────────────────────────────

export const GEOCODING_PROVIDERS = {
  /**
   * Nominatim (OSM Geocoding)
   * Free, open data. Attribution required.
   * Max 1 req/sec. Not for bulk or commercial use.
   */
  NOMINATIM: {
    id: 'nominatim',
    name: 'Nominatim (OSM)',
    baseUrl: 'https://nominatim.openstreetmap.org',
    isOpenSource: true,
    isFreeForDemo: true,
    note: 'Max 1 req/sec. Not for bulk geocoding. Attribution required.',
  },
};

export const DEFAULT_GEOCODING_PROVIDER = GEOCODING_PROVIDERS.NOMINATIM;
