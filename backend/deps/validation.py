from fastapi import HTTPException,status,Request,Depends
from pydantic import BaseModel
from typing import Optional
from ..utils.sanitizer import clean_input,is_too_long,has_suspicious_patterns,detect_url,DEFAULT_MAX_LENGTH
import re

class QueryPayload(BaseModel):
    query:str
    connection_string:Optional[str]=None
    top_k:Optional[int]=None


def validate_query_payload(payload:QueryPayload=Depends())->QueryPayload:

    cleaned=clean_input(payload.query if payload.query is not None else '')
    
    if cleaned=='':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty."
        )
    
    if is_too_long(cleaned,DEFAULT_MAX_LENGTH):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Query is too long (> {DEFAULT_MAX_LENGTH} characters). Please send a shorter query."
        )
    
    if detect_url(cleaned):
        #currently just detecting url's not removed
        #cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned).strip() 
        pass
    
    payload.query=cleaned
    return payload