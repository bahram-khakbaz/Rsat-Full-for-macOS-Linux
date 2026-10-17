from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    actor: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(120), index=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(30), default="success")
    details: Mapped[str] = mapped_column(Text, default="{}")

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")

class SiteConfig(Base):
    __tablename__ = "site_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    domain_controllers: Mapped[list["DomainControllerConfig"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )

class DomainControllerConfig(Base):
    __tablename__ = "domain_controller_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site_configs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    site: Mapped["SiteConfig"] = relationship(back_populates="domain_controllers")

class SshSwitch(Base):
    __tablename__ = "ssh_switches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(Text, default="")
    fingerprint: Mapped[str] = mapped_column(String(100), default="")

class IpamVlan(Base):
    __tablename__ = "ipam_vlans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(120))
    cidr: Mapped[str] = mapped_column(String(32))
    default_status: Mapped[str] = mapped_column(String(16), default="unknown")
    states: Mapped[str] = mapped_column(Text, default="{}")
    revision: Mapped[int] = mapped_column(Integer, default=1)

class SshLinuxServer(Base):
    __tablename__ = "ssh_linux_servers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(Text, default="")
    fingerprint: Mapped[str] = mapped_column(String(100), default="")

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db() -> None:
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
