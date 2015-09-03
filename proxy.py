import argparse
import urllib
import urllib2
import re

from flask.app import Flask
from flask import request, make_response

app = Flask(__name__)

close_head_regexp = re.compile("</head>", re.IGNORECASE)
href_regexp = re.compile("href\s?=\s?[\"']http://([\w\.]+)(/?.*?)[\"']", re.IGNORECASE | re.MULTILINE)
src_regexp = re.compile("src\s?=\s?[\"'][htps:]*//([\w\.]+)(/?.*?)[\"']", re.IGNORECASE | re.MULTILINE)


PROXY_REQUEST_HEADER_PREFIXES = [
    "x-",
    "cookie",
    "user-agent",
    "cache-control",
]

PROXY_RESPONSE_HEADER_PREFIXES = [
    "x-",
    "content-type",
    "content-disposition",
    "date",
    "expires",
    "pragma",
    "p3p",
    "set-cookie",
    "location",
    "server",
    "cache-control",
    "access-control",
]


PROXY_INJECT_SCRIPT = """<script></script>"""


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def preview(path):
    subdomain = ".".join(request.host.split(".")[:-1])
    current_host = request.host.split(".")[-1]
    preview_url = "http://%s/%s" % (subdomain, path)
    if request.args:
        preview_url += "?" + urllib.urlencode(request.args)

    outgoing_request = urllib2.Request(preview_url)

    # copy request headers
    for header, header_value in request.headers:
        for header_prefix in PROXY_REQUEST_HEADER_PREFIXES:
            if header.lower().startswith(header_prefix):
                outgoing_request.headers[header] = header_value
                break

    opener = urllib2.build_opener()
    opener.addheaders = [('Accept-Charset', 'utf-8')]

    try:
        url_response = opener.open(outgoing_request)
        raw_response = url_response.read()

    except Exception, e:
        raise e

    if url_response.headers["content-type"].startswith("text/html"):
        close_head_regexp = re.compile("</head>", re.IGNORECASE)
        raw_response = close_head_regexp.sub(
            PROXY_INJECT_SCRIPT + "</head>", raw_response, 1
        )

        raw_response = href_regexp.sub("href=\"http://\\1.%s\\2\"" % current_host, raw_response)
        raw_response = src_regexp.sub("src=\"http://\\1.%s\\2\"" % current_host, raw_response)

        re.findall(href_regexp, raw_response)

    response = make_response(raw_response)

    # copy response headers
    for header in url_response.headers:
        for header_prefix in PROXY_RESPONSE_HEADER_PREFIXES:
            if header.lower().startswith(header_prefix):
                # copy header
                response.headers[header] = url_response.headers[header]
                break

    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="debug mode, pause on exception", action="store_true")
    parser.add_argument("-b", "--bind", help="bind address", default="0.0.0.0")
    parser.add_argument("-p", "--port", help="server port", default=8005, type=int)
    parser.add_argument("-i", "--inject", help="inject script", default=None)

    args = parser.parse_args()

    if args.inject:
        with open(args.inject) as f:
            PROXY_INJECT_SCRIPT = f.read()

    app.run(host=args.bind, port=args.port, debug=args.debug)
