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

        def dmd_ephys_prep(self, stimset_name="", order="", order_name=""):
                next_sweep = self.get_next_sweep()
                order_str = self.array_to_igor_list(order)
                rec = self.send_receive("dmd_ephys_prep", [next_sweep, stimset_name, order_str, order_name])

        def start_DAQ(self): ##returns 1 if DAQ started, 0 if DAQ is running and sweep not started
                rec = self.send_receive("startDAQ", [])
                return rec['result']['value']

        def array_to_igor_list(self, array):
                out_str = ''
                for o in array.astype('str'):
                        out_str += o + ';'
                return out_str

        def send_photostim_order(self, order_array, sweep_number):
                order_str = self.array_to_igor_list(order_array)
                rec = self.send_receive("store_photostim_order", [order_str, sweep_number])

if __name__ == '__main__':
        igor_zmq = IgorZmq()
        rec = igor_zmq.send_receive("CallMe",[])
        print(rec)