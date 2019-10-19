#!/usr/bin/env python3

###########################################
#                                         #
#                "Paster"                 #
#       Simple texte sharing server       #
#                                         #
#             Etienne  SELLAN             #
#               18/10/2019                #
#                                         #
###########################################

import time
import signal
import threading
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
from socketserver import ThreadingMixIn
import os
import math
import hashlib
import requests
import json

# SETTINGS BEGIN
settings = {}
settings["url"] = "https://paster.sellan.fr"
settings["listen_address"] = "0.0.0.0"
settings["port"] = 80
settings["directory"] = "/tmp"
settings["cleaning_interval"] = 10  # minutes
settings["max_text_length"] = 1048576  # chars
settings["enable_logs"] = False
settings["logs_path"] = "/var/log"
# SETTINGS END

static_files = ['Github-ribbon.png', 'script.js', 'style.css']

def settings_initialisation():
    for setting in settings:
        # Take environment settings if defined
        if ("paster_"+setting) in os.environ:
            settings[setting] = os.environ[("paster_"+setting)]
    settings["current_directory"] = os.path.dirname(os.path.realpath(__file__))

def path_to_array(path):
    # Split path
    path_array = path.split('/')
    # Remove empty elements
    path_array = [element for element in path_array if element]
    return path_array


def array_to_path(path_array):
    # Join array
    path = '/' + '/'.join(path_array)
    return path


def write_logs(message,error=False):
    print(message)
    if settings["enable_logs"]:
        now = time.asctime(time.localtime(time.time()))
        logs_file = 'request.log' if error else 'error.log'
        logs_full_path = array_to_path(settings["logs_path"] + [logs_file])
        with open(logs_full_path, 'a') as logs:
            logs.write("{} : {}\n".format(now, message))

def path_initialisation():
    global directory
    directory = path_to_array(settings["directory"])
    directory.append("paster")
    # Create directory for Paster if not exist
    if not os.path.exists(array_to_path(directory)):
        os.makedirs(array_to_path(directory), 666)
    global logs_path
    logs_path = path_to_array(settings["logs_path"])
    logs_path.append("paster")
    # Create directory for Paster if not exist
    if not os.path.exists(array_to_path(logs_path)):
        os.makedirs(array_to_path(logs_path), 666)


def initialisation():
    settings_initialisation()
    path_initialisation()

class request_handler(BaseHTTPRequestHandler):
    def do_GET(self):  # For home page and text access
        self.request_path = path_to_array(self.path)
        if len(self.request_path) > 0:
            if self.request_path[0] in static_files:
                static_file_index = static_files.index(self.request_path[0])
                static_file_name = static_files[static_file_index]
                with open(settings["current_directory"]+'/'+static_file_name, 'rb') as static_file:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(static_file.read())
                return
        # Open HTML homepage file
        with open(settings["current_directory"]+'/'+'index.html', 'r') as homepage:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            # Send HTML page with replaced data
            html = homepage.read()
            html = html.replace("[url]", settings["url"])
            self.wfile.write(str.encode(html))
        return

    def do_POST(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST'}
        )

        if form.getvalue("text_id") and form.getvalue("encrypted_text"):
            text_id = form.getvalue("text_id")
            encrypted_text = form.getvalue("encrypted_text")
            
            if len(encrypted_text) > int(settings["max_text_length"]):  # Check text length
                self.send_response(413)  # Send error header
                self.end_headers()  # Close header
                HTML_error = "Error: Text too long (max {} chars)\n"
                HTML_error = HTML_error.format(settings["max_text_length"])
                self.wfile.write(str.encode(HTML_error))  # Return error
                return

            # Hash text_id
            file_name = hashlib.sha512(text_id.encode('utf-8')).hexdigest()
            
            # Concat the new file full path
            self.file_path = directory+[file_name]
            
            # Check if file already exist
            if os.path.exists(array_to_path(self.file_path)):
                self.send_response(409)  # Send error header
                self.end_headers()  # Close header
                HTML_error = "Error: Another text exists with the same id\n"
                self.wfile.write(str.encode(HTML_error))  # Return error
                return
            
            # Open tmp new file to write binary data
            current_file = open(array_to_path(self.file_path), "w")

            # Write content of request
            current_file.write(encrypted_text)
            current_file.close()
            
            self.send_response(200)  # Send success header
            self.send_header('Content-type', 'application/json')  # Send mime
            self.end_headers()  # Close header

            # Return new file url to user
            response = {}
            response["state"] = "OK"
            response["msg"] = "Text protected !"
            self.wfile.write(str.encode(json.dumps(response)))
            return

        elif form.getvalue("text_id"):

            text_id = form.getvalue("text_id")
            file_name = hashlib.sha512(text_id.encode('utf-8')).hexdigest()
            
            # Construct full path of the file
            self.file_path = directory + [file_name]
            
            if os.path.exists(array_to_path(self.file_path)):
                with open(array_to_path(self.file_path), 'r') as self.file:

                    self.send_response(200)
                    self.send_header("Content-Type", 'application/json')
                    self.end_headers()

                    response = {}
                    response["state"] = "OK"
                    response["encrypted_text"] = self.file.read()

                    data = json.loads(response["encrypted_text"])
                    if "options" in data:
                        if "self-destruct" in data["options"]:
                            os.remove(array_to_path(self.file_path))

                    self.wfile.write(str.encode(json.dumps(response)))
            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.response = "Text not found \n"
                self.wfile.write(str.encode(self.response))


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

def run_on(port):
    print("\n")
    print("/---------------------------------\\")
    print("|  Starting Paster on port {}  |".format(str(settings["port"]).rjust(5, " ")))
    print("\\---------------------------------/")
    print("\n")
    print("\n\nLogs : \n")
    server_address = (settings["listen_address"], int(settings["port"]))
    httpd = ThreadedHTTPServer(server_address, request_handler)
    httpd.serve_forever()


def human_readable_time(seconds):  # Convert time in seconds to human readable string format
    units = ['second', 'minute', 'hour', 'day', 'week', 'month', 'year']
    maximum_values = [60, 60, 24, 7, 4, 12, 99]
    cursor = 0
    while seconds > maximum_values[cursor]:
        seconds /= maximum_values[cursor]
        cursor += 1
    value = math.ceil(seconds)
    unit = units[cursor]
    if float(value) > 1:
        unit += 's'
    return str(value)+' '+unit


def set_interval(func, time):
    e = threading.Event()
    while not e.wait(time):
        func()


def clean_files():
    # Create list of deleted files
    removed = []
    now = time.time()

    for file in os.listdir(array_to_path(directory)):
        if os.path.isfile(array_to_path(directory+[file])):
            with open(array_to_path(directory+[file]), 'r') as f:
                delete = True
                try:
                    data = json.loads(f.read())
                    if data['deletion'] > int(now):
                        delete = False
                except:
                    pass
            if delete:
                removed.append(file)
                os.remove(array_to_path(directory+[file]))

    if len(removed) > 0:
        write_logs("Files removed : {}".format(', '.join(removed)))


if __name__ == "__main__":
    server = Thread(target=run_on, args=[int(settings["port"])])
    server.daemon = True
    server.start()
    initialisation()
    # Launch auto cleaning interval
    set_interval(clean_files, (int(settings["cleaning_interval"]) * 60))
    signal.pause()
