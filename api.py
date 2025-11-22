#!/usr/bin/env python3
"""
Egypt Voter API - REST API wrapper for the Selenium scraper
Provides endpoints to query Egyptian voter/electoral information by national ID
"""

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from typing import Optional, Dict, Any, Literal
import logging
import re
import traceback
import time
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from selenium_scraper import FreeElectionsScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Allowed districts/sections to process
ALLOWED_DISTRICTS = [
    "قسم الشرق",
    "قسم العرب",
    "قسم الضواحى",
    "قسم أول بورفؤاد",
    "قسم ثان بورفؤاد"
]


def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit. Returns True if allowed, False if blocked."""
    current_time = time.time()
    window_start = current_time - RATE_LIMIT_WINDOW

    # Clean old requests from this IP
    rate_limit_store[client_ip] = [
        timestamp for timestamp in rate_limit_store[client_ip]
        if timestamp > window_start
    ]

    # Check if under limit
    if len(rate_limit_store[client_ip]) < RATE_LIMIT_REQUESTS:
        rate_limit_store[client_ip].append(current_time)
        return True

    return False

# Global scraper instance
scraper = None

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 1000  # Max requests per window
RATE_LIMIT_WINDOW = 60     # Window in seconds (1 minute)
rate_limit_store = defaultdict(list)  # Store timestamps per client IP

# Concurrency control
MAX_CONCURRENT_REQUESTS = 3  # Allow max 3 concurrent scraper requests
request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage scraper lifecycle - initialize on startup, cleanup on shutdown"""
    global scraper
    logger.info("Initializing scraper with retry mechanism...")
    try:
        # Initialize with retry configuration and session reuse
        scraper = FreeElectionsScraper(
            headless=True,
            max_retries=3,      # Maximum retry attempts
            retry_delay=2,      # Base delay between retries (exponential backoff)
            session_timeout=300 # Keep browser session alive for 5 minutes
        )
        logger.info(f"Scraper initialized successfully with max_retries=3, scraper object: {scraper is not None}")
    except Exception as e:
        logger.error(f"Failed to initialize scraper: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        scraper = None
    
    yield
    
    # Cleanup
    logger.info("Shutting down scraper...")
    if scraper:
        try:
            scraper.close()
            logger.info("Scraper closed successfully")
        except Exception as e:
            logger.error(f"Error closing scraper: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="Egypt Voter API",
    description="API for querying Egyptian voter/electoral information by national ID",
    version="1.0.0",
    lifespan=lifespan
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """Rate limiting middleware to prevent abuse"""
    # Get client IP (handle forwarded headers)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds allowed.",
                "retry_after": RATE_LIMIT_WINDOW
            }
        )

    response = await call_next(request)
    return response


# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your security requirements
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers for clean error responses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with clean, user-friendly messages"""
    errors = exc.errors()
    
    # Extract the first error for a clean response
    if errors:
        error = errors[0]
        field = error['loc'][-1] if error['loc'] else 'unknown'
        msg = error['msg']
        
        # Clean up the message
        if msg.startswith('Value error, '):
            msg = msg.replace('Value error, ', '')
        
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": msg,
                "field": field,
                "input": error.get('input')
            }
        )
    
    # Fallback for multiple errors
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": "Validation error",
            "details": [
                {
                    "field": e['loc'][-1] if e['loc'] else 'unknown',
                    "message": e['msg'].replace('Value error, ', '')
                }
                for e in errors
            ]
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        }
    )


# Request/Response Models
class NationalIDRequest(BaseModel):
    """Request model for national ID lookup"""
    national_id: str = Field(
        ...,
        description="Egyptian national ID (exactly 14 digits)",
        json_schema_extra={"example": "29710260300314"}
    )
    
    @field_validator('national_id')
    @classmethod
    def validate_national_id(cls, v: str) -> str:
        """Validate that national ID is exactly 14 digits"""
        # Remove any whitespace
        v = v.strip()
        
        # Check length
        if len(v) != 14:
            raise ValueError(f'National ID must be exactly 14 digits, got {len(v)} characters')
        
        # Check if all characters are digits
        if not v.isdigit():
            raise ValueError('National ID must contain only digits (0-9)')
        
        return v


# Success response models
class RegisteredVoterData(BaseModel):
    """Data for a successfully registered voter"""
    electoral_center: str = Field(..., description="Electoral center name", alias="electoral_center")
    district: str = Field(..., description="District name")
    address: str = Field(..., description="Electoral center address")
    subcommittee_number: str = Field(..., description="Subcommittee number")
    electoral_list_number: str = Field(..., description="Number in electoral list")
    
    model_config = ConfigDict(populate_by_name=True)


class NotRegisteredData(BaseModel):
    """Data for voter not registered in database"""
    message: str = Field(..., description="Error message in Arabic")
    reason: str = Field(default="not_registered", description="Reason code")


class UnderageData(BaseModel):
    """Data for underage person"""
    message: str = Field(..., description="Error message in Arabic")
    reason: str = Field(default="underage", description="Reason code")


class OutOfDistrictData(BaseModel):
    """Data for voter outside target districts"""
    message: str = Field(..., description="Information message in Arabic")
    reason: str = Field(default="out_of_district", description="Reason code")
    district: str = Field(..., description="The actual district of the voter")
    electoral_center: Optional[str] = Field(None, description="Electoral center name")
    address: Optional[str] = Field(None, description="Electoral center address")


class SuccessResponse(BaseModel):
    """Success response when voter is registered"""
    success: Literal[True] = True
    national_id: str = Field(..., description="The queried national ID")
    status: Literal["registered"] = "registered"
    data: RegisteredVoterData
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "national_id": "29710260300314",
                "status": "registered",
                "data": {
                    "electoral_center": "مدرسه التربيه الفكريه الاساسيه المشتركة",
                    "district": "قسم الزهور",
                    "address": "مساكن بلال بن رباح",
                    "subcommittee_number": "20",
                    "electoral_list_number": "7881"
                }
            }
        }
    )


class NotRegisteredResponse(BaseModel):
    """Response when voter is not registered"""
    success: Literal[True] = True
    national_id: str = Field(..., description="The queried national ID")
    status: Literal["not_registered"] = "not_registered"
    data: NotRegisteredData
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "national_id": "12345678901234",
                "status": "not_registered",
                "data": {
                    "message": "الرقم القومي غير مدرج بقاعدة بيانات الناخبين",
                    "reason": "not_registered"
                }
            }
        }
    )


class UnderageResponse(BaseModel):
    """Response when person is underage"""
    success: Literal[True] = True
    national_id: str = Field(..., description="The queried national ID")
    status: Literal["underage"] = "underage"
    data: UnderageData
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "national_id": "12345678901234",
                "status": "underage",
                "data": {
                    "message": "عفوا, غير مسموح لإقل من 18 سنة بالإنتخاب",
                    "reason": "underage"
                }
            }
        }
    )


class OutOfDistrictResponse(BaseModel):
    """Response when voter is outside target districts"""
    success: Literal[True] = True
    national_id: str = Field(..., description="The queried national ID")
    status: Literal["out_of_district"] = "out_of_district"
    data: OutOfDistrictData
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "national_id": "12345678901234",
                "status": "out_of_district",
                "data": {
                    "message": "الناخب مسجل في دائرة خارج النطاق المستهدف",
                    "reason": "out_of_district",
                    "district": "قسم الزهور",
                    "electoral_center": "مدرسه التربيه الفكريه",
                    "address": "مساكن بلال بن رباح"
                }
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error response when request fails"""
    success: Literal[False] = False
    national_id: str = Field(..., description="The queried national ID")
    error: str = Field(..., description="Error message")
    retries_exhausted: Optional[bool] = Field(None, description="Whether all retry attempts were exhausted")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "national_id": "12345678901234",
                "error": "Failed after 3 attempts. Last error: Could not find iframe",
                "retries_exhausted": True
            }
        }
    )


class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    success: Literal[False] = False
    error: str = Field(..., description="Error message")
    field: str = Field(..., description="Field that failed validation")
    input: Optional[str] = Field(None, description="The invalid input value")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "National ID must be exactly 14 digits, got 13 characters",
                "field": "national_id",
                "input": "2971026000314"
            }
        }
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str


# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Egypt Voter API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="API is running"
    )


@app.post("/lookup")
async def lookup_national_id(request: NationalIDRequest):
    """
    Lookup electoral information by national ID (with automatic retry on failures)

    The API will automatically retry up to 3 times if the request fails due to:
    - Network issues
    - Timeout errors
    - Page loading issues
    - Temporary website unavailability

    Args:
        request: NationalIDRequest containing the national ID (14 digits)

    Returns:
        JSON response with electoral data or error information

    Raises:
        HTTPException: If scraper is not available or validation fails
    """
    if scraper is None:
        logger.error("Scraper not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraper service is not available. Please try again later."
        )

    national_id = request.national_id
    logger.info(f"Received lookup request for national ID: {national_id}")

    # Acquire semaphore to control concurrency
    async with request_semaphore:
        try:
            # Perform the scraping (with automatic retries and timeout)
            result = scraper.scrape_electoral_data(national_id, timeout=30)

            # Handle None result (shouldn't happen, but defensive programming)
            if result is None:
                logger.error(f"Scraper returned None for {national_id}")
                error_response = ErrorResponse(
                    success=False,
                    national_id=national_id,
                    error="Unexpected error: scraper returned no data"
                )
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=error_response.model_dump(exclude_none=True)
                )

            if result['success']:
                data = result['data']
                data_status = data.get('status', 'unknown')

                # Handle different statuses
                if data_status == 'success':
                    # Check if district is in allowed list
                    district = data.get('district', '')

                    if district and district not in ALLOWED_DISTRICTS:
                        # Voter is registered but in a district outside our target
                        response = OutOfDistrictResponse(
                            success=True,
                            national_id=national_id,
                            status="out_of_district",
                            data=OutOfDistrictData(
                                message="الناخب مسجل في دائرة خارج النطاق المستهدف",
                                reason="out_of_district",
                                district=district,
                                electoral_center=data.get('electoral_center', ''),
                                address=data.get('address', '')
                            )
                        )
                        logger.info(f"National ID {national_id} is out of target districts: {district}")
                        return JSONResponse(
                            status_code=status.HTTP_200_OK,
                            content=response.model_dump(exclude_none=True)
                        )
                    
                    # Registered voter with complete data in allowed district
                    response = SuccessResponse(
                        success=True,
                        national_id=national_id,
                        status="registered",
                        data=RegisteredVoterData(
                            electoral_center=data.get('electoral_center', ''),
                            district=district,
                            address=data.get('address', ''),
                            subcommittee_number=data.get('subcommittee_number', ''),
                            electoral_list_number=data.get('electoral_list_number', '')
                        )
                    )
                    logger.info(f"Successfully retrieved data for {national_id} in allowed district: {district}")
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content=response.model_dump(exclude_none=True)
                    )
                    
                elif data_status == 'underage':
                    # Person is underage
                    response = UnderageResponse(
                        success=True,
                        national_id=national_id,
                        status="underage",
                        data=UnderageData(
                            message=data.get('error_message', 'عفوا, غير مسموح لإقل من 18 سنة بالإنتخاب'),
                            reason="underage"
                        )
                    )
                    logger.info(f"National ID {national_id} is underage")
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content=response.model_dump(exclude_none=True)
                    )
                    
                elif data_status == 'not_registered':
                    # Not in voter database
                    response = NotRegisteredResponse(
                        success=True,
                        national_id=national_id,
                        status="not_registered",
                        data=NotRegisteredData(
                            message=data.get('error_message', 'الرقم القومي غير مدرج بقاعدة بيانات الناخبين'),
                            reason="not_registered"
                        )
                    )
                    logger.info(f"National ID {national_id} not registered")
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content=response.model_dump(exclude_none=True)
                    )
                else:
                    # Unknown status
                    error_response = ErrorResponse(
                    success=False,
                    national_id=national_id,
                    error=f"Unknown status: {data_status}"
                )
                    return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=error_response.model_dump(exclude_none=True)
                )
            else:
                # Scraping failed
                error_message = result.get('error', 'Unknown error occurred')
                retries_exhausted = result.get('retries_exhausted', False)
                
                if retries_exhausted:
                    logger.error(f"Scraping failed for {national_id} after all retries: {error_message}")
                else:
                    logger.error(f"Scraping failed for {national_id}: {error_message}")
                
                error_response = ErrorResponse(
                    success=False,
                    national_id=national_id,
                    error=error_message,
                    retries_exhausted=retries_exhausted if retries_exhausted else None
                )
                
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=error_response.model_dump(exclude_none=True)
                )
                
        except ValueError as e:
            # Validation error (should be caught by Pydantic, but just in case)
            logger.error(f"Validation error for {national_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except TimeoutError as e:
            # Timeout error
            logger.error(f"Timeout error for {national_id}: {str(e)}")
            error_response = ErrorResponse(
                success=False,
                national_id=national_id,
                error="Request timeout. The website took too long to respond.",
                retries_exhausted=True
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=error_response.model_dump(exclude_none=True)
            )
        except ConnectionError as e:
            # Network/connection error
            logger.error(f"Connection error for {national_id}: {str(e)}")
            error_response = ErrorResponse(
                success=False,
                national_id=national_id,
                error="Network connection error. Please check your internet connection and try again.",
                retries_exhausted=True
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=error_response.model_dump(exclude_none=True)
            )
        except TimeoutError as e:
            # Timeout error
            logger.error(f"Timeout error for {national_id}: {str(e)}")
            error_response = ErrorResponse(
                success=False,
                national_id=national_id,
                error="Request timed out. The service took too long to respond. Please try again.",
                retries_exhausted=True
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=error_response.model_dump(exclude_none=True)
            )
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Unexpected error during lookup for {national_id}: {str(e)}", exc_info=True)
            error_response = ErrorResponse(
            success=False,
            national_id=national_id,
            error=f"Unexpected server error: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=error_response.model_dump(exclude_none=True)
        )


@app.get("/lookup/{national_id}")
async def lookup_national_id_get(national_id: str):
    """
    Lookup electoral information by national ID (GET method)
    
    Args:
        national_id: Egyptian national ID (exactly 14 digits)
        
    Returns:
        JSON response with electoral data or error information
        
    Raises:
        HTTPException: If national ID is invalid or scraper is not available
    """
    try:
        # Validate and create request
        request = NationalIDRequest(national_id=national_id)
        return await lookup_national_id(request)
    except ValueError as e:
        # Validation error from Pydantic
        logger.error(f"Validation error for {national_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    
    # Run the API server
    logger.info("Starting Egypt Voter API server...")
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


