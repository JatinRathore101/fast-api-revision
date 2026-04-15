"""
Pydantic request and response schemas for the Company resource.

Schema overview:
  CompanyItem         → one entry in the paginated companies list
  CompanyListResponse → response for GET /companies/get-companies-list

All fields beyond `domain` are Optional because MongoDB documents in
companies_collection may omit city, state, country, and zipcode (see the
source data in app/data/companies.json).

`from_attributes=True` is set for forward compatibility but these schemas
are populated from plain dicts (MongoDB documents) rather than ORM objects.
"""

from typing import List, Optional

from pydantic import BaseModel


class CompanyItem(BaseModel):
    """
    Schema for a single company entry in the paginated companies list.

    All non-key fields are Optional to accommodate MongoDB documents that were
    ingested with partial data (e.g., missing city / state / zipcode).

    Fields:
        domain          (str):           Unique company domain identifier (always present).
        companyName     (Optional[str]): Company display name.
        companyCategory (Optional[str]): Business category.
        city            (Optional[str]): City.
        state           (Optional[str]): State or region.
        country         (Optional[str]): Country code.
        zipcode         (Optional[str]): Postal code.
    """

    domain: str
    companyName: Optional[str] = None
    companyCategory: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zipcode: Optional[str] = None

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    """
    Response schema for GET /companies/get-companies-list.

    Mirrors the shape of UserListResponse (app/schemas/user.py) for
    consistency: a paginated slice, the total document count, and a message.

    Fields:
        companies_list (List[CompanyItem]): The current page of companies.
        total_count    (int):              Total documents in the collection
                                           (across all pages) — lets clients
                                           calculate total pages without an
                                           extra request.
        message        (str):              Human-readable status message.
    """

    companies_list: List[CompanyItem]
    total_count: int
    message: str
