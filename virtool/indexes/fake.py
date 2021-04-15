from logging import getLogger
from pathlib import Path
from shutil import copy

from sqlalchemy.ext.asyncio import AsyncEngine

from virtool.fake.wrapper import FakerWrapper
from virtool.indexes.db import create, finalize
from virtool.indexes.files import create_index_file
from virtool.types import App

logger = getLogger(__name__)

INDEX_FILES = (
    "reference.fa.gz",
    "reference.1.bt2",
    "reference.2.bt2",
    "reference.3.bt2",
    "reference.4.bt2",
    "reference.rev.1.bt2",
    "reference.rev.2.bt2"
)


async def create_fake_indexes(app: App, ref_id: str, user_id: str):
    """
    Create fake indexes.

    Currently this only creates a single fake reference that includes the latest versions of the
    accompanying fake OTUs.

    TODO: Add unfinalized fake index with accompanying OTUs.

    :param app: the application object
    :param ref_id: the ID of the parent reference
    :param user_id: the ID of the creating user

    """
    db = app["db"]
    fake: FakerWrapper = app["fake"]
    settings = app["settings"]
    pg: AsyncEngine = app["pg"]

    manifest = dict()

    index_id = fake.get_mongo_id()

    await create(
        db,
        ref_id,
        user_id,
        "foo",
        index_id
    )

    data_path = Path(settings["data_path"])

    path = data_path / "references" / ref_id / index_id
    path.mkdir(parents=True)

    example_path = Path(__file__).parent.parent.parent / "example/indexes"

    for index_file  in INDEX_FILES:
        copy(example_path / index_file, path)

        await create_index_file(
            pg,
            index_id,
            "fasta" if index_file == "reference.fa.gz" else "bowtie2",
            index_file
        )

    await finalize(
        db,
        pg,
        ref_id,
        index_id
    )

    logger.debug("Created fake indexes")