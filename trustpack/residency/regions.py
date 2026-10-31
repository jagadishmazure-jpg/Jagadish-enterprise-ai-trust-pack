"""A small, hand-written region table (subset of Azure regions) used by the residency check.

geography = the Azure geography a region belongs to.
data_zone = the Microsoft Foundry data zone (US, EU, APAC) or None when the region is in no zone here.
This table is a deliberately small offline copy for tests; check the live Azure docs before relying on it.
"""
REGIONS: dict[str, dict[str, str | None]] = {
    "swedencentral": {"geography": "Sweden", "data_zone": "EU"},
    "swedensouth": {"geography": "Sweden", "data_zone": "EU"},
    "francecentral": {"geography": "France", "data_zone": "EU"},
    "francesouth": {"geography": "France", "data_zone": "EU"},
    "germanywestcentral": {"geography": "Germany", "data_zone": "EU"},
    "eastus": {"geography": "United States", "data_zone": "US"},
    "eastus2": {"geography": "United States", "data_zone": "US"},
    "westus3": {"geography": "United States", "data_zone": "US"},
    "uksouth": {"geography": "United Kingdom", "data_zone": None},
    "japaneast": {"geography": "Japan", "data_zone": "APAC"},
}

# Microsoft Foundry deployment types -> SKU code -> where inferencing data may be processed.
# Source: Microsoft Learn "Understanding deployment types in Microsoft Foundry Models" (paraphrased).
DEPLOYMENT_TYPES: dict[str, str] = {
    "GlobalStandard": "global",
    "GlobalProvisionedManaged": "global",
    "GlobalBatch": "global",
    "DeveloperTier": "global",
    "DataZoneStandard": "data_zone",
    "DataZoneProvisionedManaged": "data_zone",
    "DataZoneBatch": "data_zone",
    "Standard": "geography",
    "ProvisionedManaged": "geography",
}

# How strict each tenant boundary is. A deployment is allowed only if its scope is at least this strict.
STRICTNESS = {"global": 0, "data_zone": 1, "geography": 2}
