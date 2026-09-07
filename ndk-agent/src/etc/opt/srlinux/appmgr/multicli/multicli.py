#!/usr/bin/env python
# coding=utf-8

## Linux libraries
import grpc
import datetime
import sys
import logging
import socket
import os
import signal
import time
import threading
import json
import re
import subprocess
import netns
from typing import Any

## NDK 0.5.0 gRPC Services
import sdk_service_pb2
import sdk_service_pb2_grpc
import config_service_pb2
import telemetry_service_pb2
import telemetry_service_pb2_grpc
import route_service_pb2
import route_service_pb2_grpc
import nexthop_group_service_pb2
import nexthop_group_service_pb2_grpc
import sdk_common_pb2
import interface_service_pb2
import interface_service_pb2_grpc

agent_name = 'multicli'

# Commands:
enabled_nos_command = 'enabled-nos'
repo_url_command = 'repo-url'

# Repo and folders
tmp_dir = "/etc/opt/srlinux/cli/tmp"
cli_plugins_dir = "/etc/opt/srlinux/cli"
required_dirs = {"arista", "cisco-nx", "juniper", "nokia"}

############################################################
## Gracefully handle SIGTERM signal (SIGTERM number = 15)
## When called, will unregister Agent and gracefully exit
############################################################

def exit_gracefully(signum, frame):
    logging.info("Caught signal :: {}\n will unregister MultiCLI agent".format(signum))
    try:
        # Set global sigterm_exit to true
        global sigterm_exit
        sigterm_exit = True
        logging.info(f"Unregister Agent")

        # Unregister agent
        unregister_request = sdk_service_pb2.AgentRegistrationRequest()
        unregister_response = stub.AgentUnRegister(request=unregister_request, metadata=metadata)
        logging.info(f"Unregister response:: {sdk_common_pb2.SdkMgrStatus.Name(unregister_response.status)}")
    except grpc._channel._Rendezvous as err:
        logging.error('GOING TO EXIT NOW: {}'.format(err))
        sys.exit()

############################################################
## Keep Alive thread: send a keep every 10 seconds via gRPC call
############################################################

def send_keep_alive():
    ## exit the thread when sigterm is received
    while not sigterm_exit:
        logging.info("Send Keep Alive")
        keepalive_request = sdk_service_pb2.KeepAliveRequest()
        keepalive_response = stub.KeepAlive(request=keepalive_request, metadata=metadata)
        if keepalive_response.status == sdk_common_pb2.SdkMgrStatus.Value("SDK_MGR_STATUS_FAILED"):
            logging.error("Keep Alive failed")
        time.sleep(10)

############################################################
## Create an SDK notification stream
############################################################

def create_sdk_stream():

    # build Create request
    request=sdk_service_pb2.NotificationRegisterRequest(op=sdk_service_pb2.NotificationRegisterRequest.Operation.OPERATION_CREATE)

    # call SDK RPC to create a new stream
    notification_response = stub.NotificationRegister(request=request, metadata=metadata)

    # process the response, return stream ID if successful
    if notification_response.status == sdk_common_pb2.SdkMgrStatus.Value("SDK_MGR_STATUS_FAILED"):
        logging.error(f"Notification Stream Create failed with error {notification_response.error_str}")
        return 0
    else:
        logging.info(f"Notification Stream successful. stream ID: {notification_response.stream_id}")
        return notification_response.stream_id

############################################################
## Create a subscription to the desired notification type
############################################################

def add_sdk_subscription(stream_id, type):

    subs_request = None

    if type == 'config':
        # Build subscription request for config events
        subs_request=sdk_service_pb2.NotificationRegisterRequest(
            op=sdk_service_pb2.NotificationRegisterRequest.Operation.OPERATION_ADD_SUBSCRIPTION,
            stream_id=stream_id,
            config=config_service_pb2.ConfigSubscriptionRequest())

    if subs_request != None:
        # Call RPC
        subscription_response = stub.NotificationRegister(
            request=subs_request,
            metadata=metadata)

        logging.info(subscription_response)

        # Process response
        if subscription_response.status == sdk_common_pb2.SdkMgrStatus.Value("SDK_MGR_STATUS_FAILED"):
            logging.error(f"{type} subscription failed.")
        else:
            logging.info(f"{type} subscription successful. Stream ID: {subscription_response.stream_id}")
        return

########################################################
## Start notification stream from SDK SR Linux
#########################################################

def start_notification_stream(stream_id):

    # Build request
    request=sdk_service_pb2.NotificationStreamRequest(stream_id=stream_id)

    # Call Server Streaming SDK service
    # SR Linux will start streamning requested notifications
    notification_stream = sdk_notification_service_client.NotificationStream(request=request, metadata=metadata)

    # return the stream
    return notification_stream

############################################################
## update a object in the state datastore
## using the telemetry grpc service
## Input parameters:
## - js_path: JSON Path = the base YANG container
## - js_data: JSON attribute/value pair(s) based on the YANG model
############################################################

def update_state_datastore(js_path, js_data ):

    # create gRPC client stub for the Telemetry Service
    telemetry_stub = telemetry_service_pb2_grpc.SdkMgrTelemetryServiceStub(channel)

    # Build an telemetry update service request
    telemetry_update_request = telemetry_service_pb2.TelemetryUpdateRequest()

    # Add the YANG Path and Attribute/Value pair to the request
    telemetry_info = telemetry_update_request.states.add()
    telemetry_info.key.js_path = js_path
    telemetry_info.data.json_content = js_data

    # Log the request
    logging.info(f"Telemetry_Update_Request ::\n{telemetry_update_request}")

    # Call the telemetry RPC
    telemetry_response = telemetry_stub.TelemetryAddOrUpdate(request=telemetry_update_request,metadata=metadata)

    logging.info(f"Response: {telemetry_response.status} %%% {telemetry_response.error_str}")

    return telemetry_response

########################################################################################################################

############################################################
## Main Functions for this app:
## run_aget() & multicli_function()
############################################################

############################################################
## Agent Function
############################################################

def run_agent():

    ## Build register agent request
    register_request = sdk_service_pb2.AgentRegistrationRequest()
    register_request.agent_liveliness = 15
    register_request.auto_telemetry_state = True

    ## Call AgentRegister RPC
    register_response = stub.AgentRegister(request=register_request, metadata=metadata)

    ## Process AgentRegister response
    if register_response.status == sdk_common_pb2.SdkMgrStatus.Value("SDK_MGR_STATUS_FAILED"):
        logging.error(f"Agent Registration failed with error {register_response.error_str}")
    else:
        logging.info(f"Agent Registration successful. App ID: {register_response.app_id}")

     ## Start separate thread to send keep alive every 10 seconds
    thread = threading.Thread(target=send_keep_alive)
    thread.start()

    ## Create a new SDK notification stream
    stream_id = create_sdk_stream()

    ## Subscribe to 'config' notifications
    ## Only configuration of MultiCLI YANG data models will be received
    ## And only once they are commit into the running configuration
    add_sdk_subscription(stream_id,'config')

    ## Start listening for notifications from SR Linux

    stream_request = sdk_service_pb2.NotificationStreamRequest(stream_id=stream_id)

    # Call Server Streaming SDK service
    # SR Linux will start streamning requested notifications
    stream_response = sdk_notification_service_client.NotificationStream(request=stream_request, metadata=metadata)

    for response in stream_response:
        for notification in response.notifications:
            logging.info(f"Received Notification ::\n{notification}")
            process_notification(notification)

########################################################
## Process the received notification stream
## Only config events are expected
## Exit the loop if SIGTERM is received
#########################################################

def process_notification(notification):

    if notification.HasField("config"):

        if notification.config.HasField("data"):

            logging.info("--> Received config notification")
            logging.info(notification.config)
            data = json.loads(notification.config.data.json)

            if enabled_nos_command in data:

                logging.info(f"Selected NOS: {data[enabled_nos_command]}")
                logging.info(f"Repo URL: {data[repo_url_command]}")

                multicli_function(data[enabled_nos_command], data[repo_url_command]) # Main MultiCLI Agent Function with all the Magic!

    else:
        logging.info("--> Received unexpected notification")

    if sigterm_exit:
        ## exit loop if agent has been stopped
        logging.info("Agent Stopped Time :: {}".format(datetime.datetime.now()))
        return

def multicli_function(selected_nos, seleceted_repo_url):

    # Deleting all the files in the custom CLI commands folder. This is something we can improve!
    subprocess.run(f"rm -rf {cli_plugins_dir}/*", shell=True, check=True)

    # Confirming that a NOS has been selected
    if selected_nos != 'none':

        with netns.NetNS(nsname="srbase-mgmt"): # Using the mgmt network-instance to connect to the repo-url

            os.makedirs(tmp_dir, exist_ok=True) # Creating tmp folder
            logging.info(f"Cloning MultiCLI Repo from {seleceted_repo_url}")
            zip_path = os.path.join(tmp_dir, "repo.zip")
            try:
                # Downloading repo
                subprocess.run(["/usr/bin/curl", "-L", "--retry", "3","--retry-delay", "2","--retry-all-errors", "--connect-timeout", "10", "--max-time", "60", "-k", "-o", zip_path, seleceted_repo_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, env=os.environ)
                logging.info(f"Unzipping Repo...")

                try:
                    # Unzipping repo
                    subprocess.run(["unzip", "-o", zip_path, "-d", tmp_dir], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    logging.info(f"Unzipping Completed!")
                    # Validating zip file dynamically
                    extracted_root = None
                    for item in os.listdir(tmp_dir):
                        full = os.path.join(tmp_dir, item)
                        if os.path.isdir(full) and item.startswith("MultiCLI"):
                            extracted_root = full
                            break
                    if not extracted_root:
                        extracted_root = os.path.join(tmp_dir, "MultiCLI-main")

                    present_dirs = {name for name in os.listdir(extracted_root) if os.path.isdir(os.path.join(extracted_root, name))}
                    missing = required_dirs - present_dirs
                    if missing: # Corrupted file or a non-MultiCLI zip
                        logging.info("The downloaded MultiCLI repository is corrupted")
                        update_state_datastore(js_path='.multicli', js_data=json.dumps({"enabled-nos": selected_nos, "repo-url": seleceted_repo_url, "error-messages": "The downloaded MultiCLI repository is corrupted"}))
                    else:
                        logging.info(f"Copying files for the Selected NOS: {selected_nos}")

                        # Clean existing files and stale pycache
                        subprocess.run(f"rm -rf {cli_plugins_dir}/*", shell=True, check=True)
                        subprocess.run(f"find {cli_plugins_dir} -type d -name '__pycache__' -exec rm -rf {{}} + 2>/dev/null || true", shell=True)

                        match selected_nos:
                            case 'nokia-sros':
                                subprocess.run(f"cp -r {extracted_root}/nokia/* {cli_plugins_dir}/.", shell=True, check=True)
                                subprocess.run(f"echo 'nokia' > {cli_plugins_dir}/default_persona", shell=True, check=True)
                            case 'arista':
                                subprocess.run(f"cp -r {extracted_root}/arista/* {cli_plugins_dir}/.", shell=True, check=True)
                                subprocess.run(f"echo 'arista' > {cli_plugins_dir}/default_persona", shell=True, check=True)
                            case 'juniper':
                                subprocess.run(f"cp -r {extracted_root}/juniper/* {cli_plugins_dir}/.", shell=True, check=True)
                                subprocess.run(f"echo 'juniper' > {cli_plugins_dir}/default_persona", shell=True, check=True)
                            case 'cisco':
                                subprocess.run(f"cp -r {extracted_root}/cisco-nx/* {cli_plugins_dir}/.", shell=True, check=True)
                                subprocess.run(f"echo 'cisco' > {cli_plugins_dir}/default_persona", shell=True, check=True)
                            case 'all':
                                for d in ['arista', 'cisco-nx', 'juniper', 'nokia']:
                                    subprocess.run(f"cp -r {extracted_root}/{d}/* {cli_plugins_dir}/.", shell=True, check=True)
                                subprocess.run(f"echo 'all' > {cli_plugins_dir}/default_persona", shell=True, check=True)

                        logging.info(f"Deleting temp folder...")
                        subprocess.run(f"rm -rf {tmp_dir}", shell=True, check=True)
                        logging.info(f"MultiCLI {selected_nos} commands enabled! Enjoy!")
                        update_state_datastore(js_path='.multicli', js_data=json.dumps({"enabled-nos": selected_nos, "repo-url": seleceted_repo_url, "error-messages": "No errors"}))

                except subprocess.CalledProcessError as e:
                    logging.error(f"Failed - {zip_path}: {e.stderr.strip()}")
                    update_state_datastore(js_path='.multicli', js_data=json.dumps({"enabled-nos": selected_nos, "repo-url": seleceted_repo_url, "error-messages": "Please verify the repo-url or the ZIP file provided in the repository"}))

            except subprocess.CalledProcessError as e:
                logging.error(f"Failed: {e.stderr.strip()}")
                update_state_datastore(js_path='.multicli', js_data=json.dumps({"enabled-nos": selected_nos, "repo-url": seleceted_repo_url, "error-messages": "Verify DNS configuration and repository reachability via mgmt network-instance"}))

########################################################################################################################

############################################################
## This is executed at the time the App Mgr starts
## and runs the "maintenance.sh"
############################################################

metadata = [('agent_name', agent_name)]

## Open a GRPC channel to connect to the SR Linux sdk_mgr. sdk_mgr will be listening on 50053
channel = grpc.insecure_channel('localhost:50053')
## And create an SDK service client stub
stub = sdk_service_pb2_grpc.SdkMgrServiceStub(channel)
sdk_notification_service_client = sdk_service_pb2_grpc.SdkNotificationServiceStub(channel)

## Verify that SIGTERM signal was received
sigterm_exit = False

if __name__ == '__main__':

    ## Configure SIGTERM handler
    signal.signal(signal.SIGTERM, exit_gracefully)

    ## Configure log file
    log_filename = '/var/log/srlinux/stdout/multicli.log'
    logging.basicConfig(filename=log_filename, filemode='w',datefmt='%H:%M:%S', level=logging.INFO)
    logging.info("Agent Start Time :: {}".format(datetime.datetime.now()))

    ## Run agent function
    run_agent()
    sys.exit()
