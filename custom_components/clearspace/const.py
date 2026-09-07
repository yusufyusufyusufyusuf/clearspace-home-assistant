"""Constants for the ClearSpace integration."""

from homeassistant.const import Platform

DOMAIN = "clearspace"
CONF_API_TOKEN = "api_token"
CONF_API_URL = "api_url"
CONF_ENTITY_PREFIX = "entity_prefix"
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_IS_DEFAULT = "is_default"
DEFAULT_API_URL = "https://clearspace-billing.yusuf-145.workers.dev"
DEFAULT_ENTITY_PREFIX = "clearspace"
DEFAULT_REFRESH_INTERVAL = 60
PLATFORMS = [Platform.SENSOR]
