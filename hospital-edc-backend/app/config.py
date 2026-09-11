from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    UPLOAD_DIR: str = "./uploads"
    # 敏感字段（姓名/身份证）Fernet 加密密钥；为空则明文透传（仅限开发）
    FIELD_ENCRYPTION_KEY: str = ""
    # 多实例部署：每个项目/医院一份 .env，各自独立命名与端口
    PROJECT_NAME: str = "三一照护研究"
    PORT: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()