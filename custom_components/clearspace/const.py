"""Constants for the ClearSpace integration."""

from homeassistant.const import Platform

DOMAIN = "clearspace"
CONF_API_TOKEN = "api_token"
CONF_API_URL = "api_url"
DEFAULT_API_URL = "https://clearspace-billing.yusuf-145.workers.dev"
PLATFORMS = [Platform.SENSOR]
