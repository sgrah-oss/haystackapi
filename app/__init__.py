"""
A Flask layer to haystack interface.
"""
import logging
import os
import sys

import click

try:
    from flask import Flask, send_from_directory
except ImportError:
    # FIXME
    print("""
To start haystackapi, use
pip install "haystackapi[flask]"
or
pip install "haystackapi[flask,graphql]"
and set HAYSTACK_PROVIDER variable
HAYSTACK_PROVIDER=haystackapi.providers.ping haystackapi
""", file=sys.stderr)
    sys.exit(-1)

USE_GRAPHQL = False
try:
    import graphene
    from app.blueprint_graphql import graphql_blueprint

    USE_GRAPHQL = True
except ImportError:
    print("""
To use GraphQL,use
pip install "haystackapi[flask,graphql]"  
""", file=sys.stderr)

from app.blueprint_haystack import haystack_blueprint as haystack_blueprint

app = Flask(__name__)
_log_level = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig(level=_log_level)
app.logger.setLevel(_log_level)
app.register_blueprint(haystack_blueprint)
if USE_GRAPHQL:
    app.register_blueprint(graphql_blueprint)


@app.route('/')
def index():
    """
    Empty page to check the deployment
    """
    return "Flask is up and running"


@app.route('/favicon.ico')
def favicon():
    """
    Return the favorite icon
    """
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@click.command()
@click.option('-h', '--host', default='0.0.0.0')
@click.option('-p', '--port', default=3000)
def main(host, port) -> int:
    """
    Stack a flask server.
    The command line must set the host and port.
    """
    debug = (os.environ.get("FLASK_DEBUG", "0") == "1")
    app.run(host=host if not debug else 'localhost',
            port=port,
            debug=debug)
    return 0


if __name__ == '__main__':
    sys.exit(main())  # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
