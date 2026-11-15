from pydantic import BaseModel, Field

class AgentTestRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)

class ProfileUpdate(BaseModel):
    full_name: str = Field(default="", max_length=150)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    location: str = Field(default="", max_length=120)
    target_role: str = Field(default="", max_length=120)
