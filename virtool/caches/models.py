from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.sql.schema import UniqueConstraint

from virtool.pg.utils import Base
from virtool.samples.models import ArtifactType


class SampleArtifactCache(Base):
    """
    SQL model to store a cached sample artifact

    """
    __tablename__ = "sample_artifacts_cache"

    id = Column(Integer, primary_key=True)
    sample = Column(String, nullable=False)
    name = Column(String, nullable=False)
    name_on_disk = Column(String)
    size = Column(Integer)
    type = Column(Enum(ArtifactType), nullable=False)
    uploaded_at = Column(DateTime)


class SampleReadsCache(Base):
    """
    SQL model to store cached sample reads files

    """
    __tablename__ = "sample_reads_cache"
    __tableargs__ = (UniqueConstraint("sample", "name"),)

    id = Column(Integer, primary_key=True)
    sample = Column(String, nullable=False)
    name = Column(String(length=13), nullable=False)
    name_on_disk = Column(String, nullable=False)
    size = Column(Integer)
    uploaded_at = Column(DateTime)