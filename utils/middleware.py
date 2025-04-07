import os
import jwt
from starlette.responses import JSONResponse
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Example verify_token function
def verify_token(token: str) -> dict:
    secret_key = os.environ.get("JWT_SIGNING_KEY")
    try:
        # Ensure the token is valid and return the decoded payload
        decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# Define the TokenVerificationMiddleware
class TokenVerificationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Retrieve the token from the Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[len("Bearer "):]
            else:
                token = auth_header
            try:
                # Verify the token and attach decoded data to the request state
                decoded = verify_token(token)
                request.state.decoded_token = decoded
                request.state.token = token  # also pass the raw token if needed
            except Exception as e:
                return JSONResponse(status_code=401, content={"detail": str(e)})
        else:
            request.state.decoded_token = None
        return await call_next(request)
