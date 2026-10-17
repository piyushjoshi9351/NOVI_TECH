"""Validation responses for routes that accept credentials."""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute


class SensitiveRequestRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validated(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # FastAPI normally includes the rejected input. A root/body
                # error can contain the whole credential payload, so omit input
                # and validator context for every error on these routes.
                detail = [
                    {key: error[key] for key in ("type", "loc", "msg")}
                    for error in exc.errors()
                ]
                raise HTTPException(status_code=422, detail=detail) from None

        return validated
