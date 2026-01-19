from middleware import mw_tracker, MWOptions, record_exception
from fastapi import FastAPI
from app.routes import user
import sys


# tracker = mw_tracker(
#      MWOptions(
#         # access_token="yoyntxtvjzuckjpeoekhhpfukggelwbioggm",
#         access_token="xbqiunvwxdnksvtucxdywxehecupgqnawjxy",
#         service_name="Bajrang-python-app",
#         # target="https://ruplp.middleware.io:443",
#         target="https://d232-103-156-143-126.ngrok-free.app:443",
#         otel_propagators = "b3,tracecontext",
#         custom_resource_attributes="call_id=12345678, request_id=987654321",
#         console_exporter=True,  # add to console log telemetry data
#         log_level="DEBUG",
#         collect_traces = True,  
#         collect_metrics = False,
#         collect_logs = False,
#         collect_profiling=False,
#         debug_log_file=True,
#      )
#  )


def create_application():
    application = FastAPI()
    application.include_router(user.user_router)
    application.include_router(user.guest_router)
    application.include_router(user.auth_router)
    return application


app = create_application()


@app.get("/")
async def root():
    try:
        return {"message": "Hi, I am Describly. Awesome - Your setrup is done & working."}
    except Exception as e:
        sys.excepthook(type(e), e, e.__traceback__)
        raise e
