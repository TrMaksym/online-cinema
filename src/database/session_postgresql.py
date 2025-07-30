from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.config.settings import DevSettings

settings = DevSettings()

engine = create_async_engine(settings.DATABASE_URL, echo=True, future=True)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)