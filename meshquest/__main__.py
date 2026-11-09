"""Run the dev server with: python -m meshquest"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("meshquest.app:app", host="127.0.0.1", port=8000, reload=False)
