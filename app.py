#!/usr/bin/env python3

from flask import Flask, request
from flask import jsonify
from flask import Response
import logging
import json
import sys
import os
from dotenv import load_dotenv
import paramiko
import time


load_dotenv()

CISCO_ADDR = os.getenv('CISCO_ADDR')
CISCO_USER = os.getenv('CISCO_USER')
CISCO_PASS = os.getenv('CISCO_PASS')

if not all([CISCO_ADDR, CISCO_USER, CISCO_PASS]):
    try:
        with open('.env', 'r') as env_file:
            for line in env_file:
                key, value = line.strip().split('=')
                if key == 'CISCO_ADDR':
                    CISCO_ADDR = value
                elif key == 'CISCO_USER':
                    CISCO_USER = value
                elif key == 'CISCO_PASS':
                    CISCO_PASS = value
    except FileNotFoundError:
        pass

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

max_buffer = 65535



def __cisco_clear_buffer(ssh_connection):
    if ssh_connection.recv_ready():
        return ssh_connection.recv(max_buffer)

def __cisco_command(ssh_connection, cmd):
    ssh_connection.send("{}\n".format(cmd))
    time.sleep(.5)
    return(ssh_connection.recv(max_buffer).decode())

def __cisco_connect(action="get", portNum=None, powerState=None):
    ssh = paramiko.client.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(CISCO_ADDR, username=CISCO_USER, password=CISCO_PASS,
                    disabled_algorithms=dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256"]),
                    allow_agent=False, look_for_keys=False)
        logging.info("SSH Connected successfully.")
        connection = ssh.invoke_shell()
        logging.info("Shell invoked successfully.")
        __cisco_clear_buffer(connection)
        time.sleep(1)
        connection.send("terminal length 0\n")
        __cisco_clear_buffer(connection)
        
        if action == "get":
            output = __cisco_command(connection, 'show running-config interface gigabitEthernet 1/0/{}'.format(portNum))
            __cisco_command(connection, "exit")
            if "power inline never" in output.lower():
                return jsonify({"status": "stopped"}) 
            else:
                return jsonify({"status": "running"})
            
        elif action == "set":
            if isinstance(portNum, int) and isinstance(powerState, bool):
                command_to_execute = ""
                if powerState:
                    command_to_execute = "no power inline NEVER"
                    time.sleep(1)
                    resulting_state = "running"
                elif not powerState:
                    command_to_execute = "power inline NEVER"
                    resulting_state = "stopped"
                __cisco_command(connection, 'conf t')
                __cisco_command(connection, 'interface gigabitEthernet 1/0/{}'.format(portNum))
                __cisco_command(connection, command_to_execute)
                __cisco_command(connection, "exit")
                __cisco_command(connection, "exit")
                __cisco_command(connection, "exit")
                time.sleep(1)
                return jsonify({"status": resulting_state}) 
            else:
                print("UH OH")
                raise Exception

    except paramiko.AuthenticationException:
        logging.error("Incorrect password for Paramiko!")
    except Exception as e:
        logging.error("Other exception! {}".format(e))
        


app = Flask(__name__)

@app.route('/setpower', methods=['POST'])
def setpower():
    if request.method == 'POST':
        try:
            portnum = int(request.args.get('portNum'))
            powerstate = json.loads(request.args.get('powerState').lower())
            logging.info("Received arguments: portNum: {}, powerState: {}".format(portnum, powerstate))
            result = __cisco_connect(action="set", portNum=portnum, powerState=powerstate)
        except:
            logging.warning("Malformatted arguments!")
        return result
    
@app.route('/getpower', methods=['GET'])
def getpower():
    if request.method == 'GET':
        try:
            portnum = int(request.args.get('portNum'))
            result = __cisco_connect(action="get", portNum=portnum)
        except:
            logging.warning("Malformatted arguments!")
        return result
        

app.run(host='0.0.0.0', port=8000)