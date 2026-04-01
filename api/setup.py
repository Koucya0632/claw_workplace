from setuptools import find_packages, setup


# 這個 setup.py 是給舊版 pip 的 editable 安裝相容層使用。
# 新版 pip 會優先走 pyproject.toml；舊版 pip 則可以退回 setup.py develop。
setup(
    name="openclaw-api",
    version="0.1.0",
    description="OpenClaw Smart Office Phase 1 API",
    python_requires=">=3.9",
    packages=find_packages(include=["app", "app.*"]),
    install_requires=[
        "fastapi>=0.115.0",
        "httpx>=0.27.0",
        "openpyxl>=3.1.0",
        "pydantic>=2.8.0",
        "pydantic-settings>=2.3.0",
        "python-docx>=1.1.0",
        "pypdf>=4.3.0",
        "python-multipart>=0.0.9",
        "uvicorn[standard]>=0.30.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.2.0",
        ]
    },
)

