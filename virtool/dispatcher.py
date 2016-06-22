import json
import traceback
import logging
import tornado.concurrent
import tornado.websocket
import tornado.gen
import tornado.ioloop

import virtool.gen
import virtool.jobs
import virtool.samples
import virtool.viruses
import virtool.history
import virtool.indexes
import virtool.hosts
import virtool.users
import virtool.groups
import virtool.gen
import virtool.files

COLLECTIONS = [
    "jobs",
    "samples",
    "viruses",
    "history",
    "indexes",
    "hosts",
    "groups",
    "users"
]

logger = logging.getLogger(__name__)

class Dispatcher:
    """
    Handles all websocket communication with clients. New :class:`.Transaction` objects are generated from incoming
    messages and passed to `exposed methods <exposed-methods>`_. When exposed methods return, the transactions are
    fulfilled and returned to the client.

    The dispatcher also instantiates most of Virtool's :class:`~.database.Collection` subclasses, an instance of
    :class:`.files.Manager`, and an instance of :class:`.files.Watcher`.

    """

    def __init__(self, server):
        #: A reference to the server that instantiated the :class:`.Dispatcher` object and is the parent object of the
        #: dispatcher.
        self.server = server

        #: The shared :class:`~.virtool.settings.Settings` object created by the server. Passed to all collections.
        self.settings = server.settings

        #: A :class:`~.virtool.files.Watcher` object that keeps track of what files are in the watch folder and host
        #: FASTA folder and sends changes to listening clients.
        self.watcher = virtool.files.Watcher(self)

        #: An instance of :class:`virtool.files.Manager`. Used for managing uploads and downloads.
        self.file_manager = virtool.files.Manager(self.server)

        #: A dict containing all :class:`~.database.Collection` objects available on the server, with their
        #: ``collection_name`` attributes as keys.
        self.collections = {module: getattr(virtool, module).Collection for module in COLLECTIONS}

        # Instantiate all the Collection objects.
        if self.settings.get("server_ready"):
            for collection_name in COLLECTIONS:
                self.collections[collection_name] = self.collections[collection_name](self)

        # Add self.settings to the collections dict so its methods can be exposed through the dispatcher.
        self.collections["settings"] = self.settings

        #: A list of all active connections (:class:`.SocketHandler` objects).
        self.connections = list()

        # Calls the ping method on the next IOLoop iteration.
        self.server.add_periodic_callback(self.ping, 10000)

    def handle(self, message, connection):
        """
        Handles all inbound messages from websocket clients. Messages have the form:

        +----------------+-----------------------------------------------------------------------+
        | Key            | Description                                                           |
        +================+=======================================================================+
        | tid            | the id for the transaction, which is unique on the requesting host.   |
        +----------------+-----------------------------------------------------------------------+
        | methodName     | the name of the exposed method to call.                               |
        +----------------+-----------------------------------------------------------------------+
        | collectionName | the name of the collection that the exposed method is a member of     |
        +----------------+-----------------------------------------------------------------------+
        | data           | the data the exposed method should use to do its work                 |
        +----------------+-----------------------------------------------------------------------+

        :param message: a JSON-formatted message string from a connected client.
        :type message: str

        :param connection: the connection that received the message.
        :type connection: :class:`.web.SocketHandler`

        """
        # Create a transaction based on the message.
        transaction = Transaction(self, connection, message)

        # Log a string of the format '<username> (<ip>) request <collection>:<method>' to describe the request.
        logger.info('{} ({}) requested {}.{}'.format(
            connection.user["_id"],
            connection.ip,
            transaction.collection_name,
            transaction.method_name
        ))

        # Get the requested collection if possible, otherwise log warning and return.
        try:
            collection = self.collections[transaction.collection_name]
        except KeyError:
            if transaction.collection_name == "dispatcher":
                collection = self
            else:
                logger.warning("User {} specified unknown collection {}".format(
                    connection.user["_id"],
                    transaction.collection_name
                ))
                return

        # Get the requested method if possible, otherwise log warning and return.
        try:
            method = getattr(collection, transaction.method_name)
        except AttributeError:
            logger.warning("User {} attempted unknown request {}.{}".format(
                connection.user["_id"],
                transaction.collection_name,
                transaction.method_name
            ))
            return False

        # Log warning and return if method is not exposed.
        if not hasattr(method, "is_exposed") or not method.is_exposed:
            logger.warning("User {} attempted to call unexposed method {}.{}".format(
                connection.user["_id"],
                transaction.collection_name,
                transaction.method_name
            ))
            return

        if not connection.authorized and not method.is_unprotected:
            logger.warning("Unauthorized connection at {} attempted to call protected method {}.{}".format(
                connection.ip,
                transaction.collection_name,
                transaction.method_name
            ))
            return

        # Call the exposed method if it is unprotected or the requesting connection has been authorized.
        if connection.authorized or method.is_unprotected:
            try:
                result = method(transaction)
            except TypeError:
                result = method()

            if isinstance(result, tornado.concurrent.Future):
                self.server.loop.add_future(result, handle_future)

    def dispatch(self, message, connections=None):
        """
        Dispatch a ``message`` with a conserved format to a selection of active ``connections``
        (:class:`.SocketHandler` objects). Messages are dicts with the scheme:

        +----------------+-----------------------------------------------------------------------+
        | Key            | Description                                                           |
        +================+=======================================================================+
        | operation      | a word used to tell the client what to do in response to the message. |
        +----------------+-----------------------------------------------------------------------+
        | collectionName | the name of the collection the client should perform the operation on |
        +----------------+-----------------------------------------------------------------------+
        | data           | test                                                                  |
        +----------------+-----------------------------------------------------------------------+

        :param message: the message to dispatch
        :type message: dict or list

        :param connections: the connection(s) (:class:`.SocketHandler` objects) to dispatch the message to.
        :type connections: list

        """
        base_message = {
            "operation": None,
            "collection_name": None,
            "data": None
        }

        base_message.update(message)

        # If the connections parameter was not set, dispatch the message to all authorized connections.
        connections = connections or filter(lambda conn: conn.authorized, self.connections)

        # Send the message to all appropriate websocket clients.
        for connection in connections:
            connection.write_message(base_message)

    @virtool.gen.coroutine
    def ping(self):
        """
        Sends a ping message to the client to keep the connection alive. Added as a periodic callback using
        :meth:`.Application.add_periodic_callback` as soon as the dispatcher is created. Called every three seconds.

        """
        self.dispatch({
            "operation": "ping",
            "collection": None,
            "data": None
        })

    @virtool.gen.exposed_method([])
    def listen(self, transaction):
        """
        Listen to file updates associated with the watcher name passed in the transaction.

        :param transaction: the transaction generated by the request.
        :type transaction: :class:`.Transaction`

        :return: a boolean indicating success and ``None``.
        :rtype: tuple

        """
        self.watcher.add_listener(transaction.data["name"], transaction.connection)

        return True, None

    @virtool.gen.exposed_method([])
    def unlisten(self, transaction):
        """
        Stop listening to file updates associated with the watcher name passed in the transaction.

        :param transaction: the transaction generated by the request.
        :type transaction: :class:`.Transaction`

        :return: a boolean indicating success and ``None``.
        :rtype: tuple

        """
        self.watcher.remove_listener(transaction.data["name"], transaction.connection)

        return True, None

    @virtool.gen.exposed_method([])
    def sync(self, transaction):
        """
        This exposed method will be requested by the client soon after a its connection is authorized. The client passes
        manifests of all the minimal documents it has stored locally for each collection. This allows the collections to
        send update and remove operations to the client to bring its local collections in line with those on the server.

        Calling this method also sends a current list of all host FASTA files and read files to the client.

        :param transaction: the transaction generated from the request.
        :type transaction: :class:`.Transaction`

        :return: a boolean indicating success and the total number of operations performed.
        :rtype: tuple

        .. note::

            Only users with the appropriate permissions will receive syncing dispatches from the users and groups
            collections. These collections are not retained in browser storage.

        """
        permissions = transaction.connection.user["permissions"]

        # A list of collection names to sync with the client.
        sync_list = list(["jobs", "samples", "hosts", "viruses", "history", "indexes"])

        # Only sync users and groups if the user has the appropriate permissions.
        if "modify_options" in permissions:
            sync_list.append("users")
            sync_list.append("groups")

        # Count how many operations (dispatches) were required to perform the sync. This information will be sent to the
        # client so it knows how many dispatches to expect. This helps to render a progress bar for syncing to the user.
        total_operation_count = 0

        # Sync the host FASTA and read file lists.
        for name in ["reads", "files"]:
            for file_document in self.watcher.files[name].values():
                self.dispatch({
                    "operation": "update",
                    "collection_name": name,
                    "data": file_document,
                    "sync": True
                }, [transaction.connection])

        # Sync the true collection objects.
        for name in sync_list:
            operation_count = yield self.collections[name].sync(
                transaction.data["manifests"][name],
                transaction.connection
            )

            total_operation_count += operation_count

        return True, total_operation_count

    @virtool.gen.exposed_method(["modify_options"])
    def reload(self, transaction):
        """
        Reload the server by calling :meth:`.Application.reload`. See that method's documentation for more information.

        :param transaction: the transaction generated by the request.
        :type transaction: :class:`.Transaction`

        :return: a boolean indicating success and ``None``.
        :rtype: tuple

        """
        yield self.server.reload()

        return True, None

    @virtool.gen.exposed_method(["modify_options"])
    def shutdown(self, transaction):
        """
        Shutdown the server by calling :func:`sys.exit` with an exit code of 0.

        :param transaction: the transaction generated by the request.
        :type transaction: :class:`.Transaction`

        .. note::

            The passed transaction is not fulfilled for this exposed method because :func:`sys.exit` is called before
            the method can return.

        """
        yield self.server.shutdown(0)

class Transaction:

    """
    Transactions represent websocket exchanges between the client and server. When a message is received,
    :meth:`Dispatcher.handle` is called, immediately generated a new :class:`.Transaction` object. The
    `exposed method <exposed-method>`_ requested by the client is then called and passed the transaction as the sole
    parameter.

    **All exposed methods return a tuple containing a boolean indicator of success and any data that should be returned
    to the requesting client**.

    The :meth:`.Transaction.fulfill` method is called when the exposed method completes to
    send the information back to the client.

    The transaction is identified by a transaction ID (TID) generated by the client. When it is fulfilled and returned
    to the client, the client can identify the transaction by its :abbr:`TID (transaction ID)` and call any functions
    bound to success or failure of the request.

    """
    def __init__(self, dispatcher, connection, message):

        #: The raw message from the client converted to dict from JSON.
        self.message = json.loads(message)

        #: The :class:`.SocketHandler` object to send a reply through. If it is set to None, the message will be
        #: broadcast.
        self.connection = connection

        #: The dispatcher that spawned the transaction. Referred to for broadcasting a result to all registered
        #: connections
        self.dispatcher = dispatcher

        #: The :abbr:`TID (transaction ID)` generated for the transaction by the requesting client.
        self.tid = self.message["tid"]

        try:
            #: The name of the exposed method to call.
            self.method_name = self.message["methodName"]
        except KeyError:
            raise KeyError("Message dict used to create Transaction must contain methodName key.")

        #: The name of the collection or object containing the exposed method to call.
        self.collection_name = self.message["collectionName"] if "collectionName" in self.message else None

        #: The data to be used for calling the exposed method.
        self.data = self.message["data"] if "data" in self.message else None

        #: An attribute that can be reassigned to send data to the client when the transaction is fulfilled without
        #: passing data directly to :meth:`.fulfill`.
        self.response = None

    def fulfill(self, success=True, data=None):
        """
        Called when the exposed method specified by :attr:`.method_name` returns. Sends a message to the client telling
        it whether the transaction was successful and sending any data returned by the exposed method.

        :param success: indicates whether the transaction succeeded.
        :type success: bool

        :param data:
        :type data: dict or list

        """
        data = data or self.response

        if not success:
            data_to_send = {
                "warning": True,
                "message": "Error"
            }

            if data:
                data_to_send.update(data)

            data = data_to_send

        self.dispatcher.dispatch({
            "operation": "transaction",
            "data": {
                "tid": self.tid,
                "success": success,
                "data": data
            }
        }, [self.connection])


def handle_future(future):
    try:
        future.result()
    except Exception:
        print(traceback.format_exc())