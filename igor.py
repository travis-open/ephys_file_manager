import json
import zmq

##formatCall from ACQ4 https://github.com/campagnola/acq4/blob/main/acq4/util/igorpro.py
##TODO: consider import from ACQ4, additional dependencies?

class IgorZmq(object):

        def __init__(self):
                self._context = zmq.Context()
                self._socket = self._context.socket(zmq.REQ)
                self._socket.connect("tcp://127.0.0.1:5555")

        def format_call(self, cmd, params, messageID):
                call = {"version": 1,
                "messageID": messageID,
                "CallFunction": {
                    "name": cmd,
                    "params": params}
                }
                msg = json.dumps(call)
                return msg

        def call(self, msg):
                self._socket.send_string(msg)  
                
        def receive(self):
                rec = self._socket.recv_json()
                return rec
        
        def send_receive(self, cmd, params):
                msg = self.format_call(cmd, params, "messageID")
                self.call(msg)
                rec = self.receive()
                return rec

        def get_next_sweep(self):
                rec = self.send_receive("getNextSweep", [])
                return rec['result']['value']

        def get_DAQ_status(self):
                rec = self.send_receive("isDAQhappening", [])
                return rec['result']['value']

        def dmd_ephys_prep(self):
                rec = self.send_receive("dmd_ephys_prep", [])

        def start_DAQ(self): ##returns 1 if DAQ started, 0 if DAQ is running and sweep not started
                rec = self.send_receive("startDAQ", [])
                return rec['result']['value']

if __name__ == '__main__':
        igor_zmq = IgorZmq()
        rec = igor_zmq.send_receive("CallMe",[])
        print(rec)


#context=zmq.Context()
#socket = context.socket(zmq.REQ)
#socket.connect("tcp://127.0.0.1:5555")
#time.sleep(0.2)
#func_name = "CallMe" # The name of the Igor function we want to call
#func_params = [] # The arguments to that function
# A command sent over a ZeroMQ socket to call a function
#command = {"version": 1, # Version of the protocol
           #"CallFunction": # The action to do (call an Igor function)
                #{"name": func_name, # The name of the Igor function
                 #"params": func_params} # The arguments to that function
          #}
#command_str = json.dumps(command) # JSONify it

# #def formatCall(cmd, params, messageID):
#         #call = {"version": 1,
#                 "messageID": messageID,
#                 "CallFunction": {
#                     "name": cmd,
#                     "params": params}
#                 }
#         msg = json.dumps(call)
#         return msg
# messageID="testMess"
# call=formatCall(func_name, params=func_params, messageID=messageID)
#socket.send_string(call)
#socket.send_string(command_str) # Send that command over the socket to Igor
#rec = socket.recv_json()
#print(rec)