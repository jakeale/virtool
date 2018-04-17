from virtool.utils import random_alphanumeric


def apply_projection(document, projection):
    """
    Apply a Mongo-style projection to a document and return it.

    :param document: the document to project
    :type document: dict

    :param projection: the projection to apply
    :type projection: Union[dict,list]

    :return: the projected document
    :rtype: dict

    """
    if isinstance(projection, list):
        if "_id" not in projection:
            projection.append("_id")

        return {key: document[key] for key in projection}

    if not isinstance(projection, dict):
        raise TypeError("Invalid type for projection: {}".format(type(projection)))

    if projection == {"_id": False}:
        return {key: document[key] for key in document if key != "_id"}

    if "_id" not in projection:
        projection["_id"] = True

    return {key: document[key] for key in document if projection.get(key, False)}


async def get_new_id(collection, excluded=None):
    """
    Returns a new, unique, id that can be used for inserting a new document. Will not return any id that is included
    in ``excluded``.

    :param collection: the Mongo collection to get a new _id for
    :type collection: :class:`motor.motor_asyncio.AsyncIOMotorCollection`

    :param excluded: a list of ids to exclude from the search
    :type excluded: Union[None, list]

    :return: an id unique to the collection
    :rtype: str

    """
    excluded = set(excluded) or set()

    excluded += set(await collection.distinct("_id"))

    return random_alphanumeric(length=8, excluded=list(excluded))


async def get_one_field(collection, field, query):
    projected = await collection.find_one(query, [field])

    if projected is None:
        return None

    return projected[field]


async def get_non_existent_ids(collection, id_list):
    existing_group_ids = await collection.distinct("_id", {"_id": {"$in": id_list}})
    return set(id_list) - set(existing_group_ids)


async def id_exists(collection, _id):
    """
    Check if the document id exists in the collection.

    :param collection: the Mongo collection to check the _id against
    :type collection: :class:`motor.motor_asyncio.AsyncIOMotorCollection`

    :param _id: the _id to check for
    :type _id: str

    :return: ``bool`` indicating if the user exists
    :rtype: bool

    """
    return bool(await collection.count({"_id": _id}))
