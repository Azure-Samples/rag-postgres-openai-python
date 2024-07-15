from collections import namedtuple

from azure.core.credentials import TokenCredential

MockToken = namedtuple("MockToken", ["token", "expires_on"])


class MockAzureCredential(TokenCredential):
    def get_token(self, uri):
        return MockToken("", 9999999999)


class MockAzureCredentialExpired(TokenCredential):
    def __init__(self):
        self.access_number = 0

    async def get_token(self, uri):
        self.access_number += 1
        if self.access_number == 1:
            return MockToken("", 0)
        else:
            return MockToken("", 9999999999)
