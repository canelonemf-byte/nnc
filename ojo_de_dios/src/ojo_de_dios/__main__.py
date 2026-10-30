"""Run: python -m ojo_de_dios"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("ojo_de_dios.api:app", host="127.0.0.1", port=8080, reload=False)
