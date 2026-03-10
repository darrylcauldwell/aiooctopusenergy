"""Exceptions for the Octopus Energy API client."""


class OctopusEnergyError(Exception):
    """Base exception for Octopus Energy API errors."""


class OctopusEnergyAuthenticationError(OctopusEnergyError):
    """Raised when authentication fails (invalid API key)."""


class OctopusEnergyNotFoundError(OctopusEnergyError):
    """Raised when the requested resource is not found."""


class OctopusEnergyRateLimitError(OctopusEnergyError):
    """Raised when the API returns HTTP 429 (Too Many Requests)."""


class OctopusEnergyConnectionError(OctopusEnergyError):
    """Raised when unable to connect to the API."""


class OctopusEnergyTimeoutError(OctopusEnergyError):
    """Raised when a request to the API times out."""
