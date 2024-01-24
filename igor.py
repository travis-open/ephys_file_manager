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

        def get_mies_name(self):
                rec = self.send_receive("getMIESname", [])
                return rec['result']['value']

        def get_DAQ_status(self):
                rec = self.send_receive("isDAQhappening", [])
                return rec['result']['value']

        def dmd_sequence_ephys_prep(self, stimset_name="", order="", order_name="", sweep_reps=1, n_images=1, seq_int=100):
                next_sweep = self.get_next_sweep()
                order_str = self.array_to_igor_list(order[:120])
                if len(order)>120:
                        order_str = order_str + "order truncated see photostim_log;"
                ##note: use of order_str to send the order of stimuli to Igor works for n<=120, breaks when n~>248. (Python hangs waiting to receive Igor message.) 
                ##Directly calling (within Igor console) the Igor function dmd_sequence_ephys_prep with large string pasted works OK. Appears the function never is called when
                ##using ZMQ with a long order_str. Cursory reading of pyzmq doc's suggest message limit is very large and not the issue. Issue with Igor XOP?
                ##As pilot analyses are ongoing in Python using photostim_log.json and nwb (rather than Igor), and full-fledged work will likely stay there,
                ##here I truncate the order as temp fix. Alts for future - have look-up table for Igor to convert order_name to order; point Igor to photostim_log.json
                ##or other file to read in order. Explore sending arrays to Igor as arguments via zmq (conversion to string found to be most viable solution initially).
                rec = self.send_receive("dmd_sequence_ephys_prep", [next_sweep, stimset_name, order_str, order_name, sweep_reps, n_images, seq_int])
                

        def dmd_frame_ephys_prep(self, stimset_name="", order="", order_name="", sweep_reps=1):
                next_sweep = self.get_next_sweep()
                order_str = self.array_to_igor_list(order)
                rec = self.send_receive("dmd_frame_ephys_prep", [next_sweep, stimset_name, order_str, order_name, sweep_reps])

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