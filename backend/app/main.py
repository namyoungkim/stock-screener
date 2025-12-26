from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Stock Screener API",
    description="Value investing screening tool for US and Korean stocks",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=["*"],  # TODO: Update in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Stock Screener API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
