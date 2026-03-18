from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

class ProfileExtraction(BaseModel):
    profession: str = Field(description="The job title or profession mentioned", default=None)
    skills: str = Field(description="A comma-separated list of skills mentioned", default=None)
    location: str = Field(description="The city or place name mentioned", default=None)

llm = ChatOpenAI(
    model="llama-3.3-70b-versatile",
    temperature=0,
    base_url=os.getenv("OPENAI_API_BASE"),
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

parser = JsonOutputParser(pydantic_object=ProfileExtraction)
prompt = ChatPromptTemplate.from_messages([
    ("system", "Extract profession, skills, and location. Return null if missing. {format_instructions}"),
    ("human", "{text}")
])

extraction_chain = prompt | llm | parser

def extract_profile_data(text):
    try:
        result = extraction_chain.invoke({
            "text": text,
            "format_instructions": parser.get_format_instructions()
        })
        return result
    except Exception as e:
        print(f"❌ Extraction Error: {e}")
        return None