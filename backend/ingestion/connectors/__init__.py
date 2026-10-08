from .branch_csv import BranchCsvConnector
from .flexcube import FlexcubeConnector
from .salesforce import SalesforceConnector

# Every connector Lumina knows, by Source.code. Add new connectors here.
CONNECTORS = {
    connector.source_code: connector
    for connector in [FlexcubeConnector, SalesforceConnector, BranchCsvConnector]
}
