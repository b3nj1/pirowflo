import threading
import time
import datetime

import WaterrowerInterface

'''
We register 3 callback function to the WaterrowerInterface with the event as input. Those function get exectuted 
as soon as an event is register from "capturing". 
We create 3 differnt dict with 3 different value sets. 
- first case: rowing has been reseted so only 0 value should be send even if in the WR memory old values persists 
- second case: we do HIIT training and the rower is at standstill. The value are not set to 0 in the WR memory. therfore set all instantaneous value to 0 e.g power, pace, stroke rate 
- last case: Normal rowing get data from WR memory without touching it 

Depeding on thoses cases send to the bluetooth module only the value dict with the correct numbers. 
'''

IGNORE_LIST = ['graph', 'tank_volume', 'display_sec_dec']


class DataLogger(object):
    def __init__(self, rower_interface):
        self._rower_interface = rower_interface
        self._rower_interface.register_callback(self.on_rower_event)
        self._rower_interface.register_callback(self.pulse)
        self._rower_interface.register_callback(self.reset_requested)
        self._event = {}
        self._events = []
        self._activity = None
        self._stop_event = threading.Event()
        self.Lastcheckforpulse = 0
        self.PulseEventTime = 0
        self.DeltaPulse = 0
        self.PaddleTurning = False
        self.rowerreset = True
        self.WRValues_rst = {
                'stroke_rate': 0,
                'total_strokes': 0,
                'total_distance_m': 0,
                'instantaneous pace': 65534,
                'watts': 0,
                'total_kcal': 0,
                'total_kcal_hour': 0,
                'total_kcal_min': 0,
                'heart_rate': 0,
                'elapsedtime': 0.0,
            }
        self.WRValues = self.WRValues_rst
        self.WRvalue_standstill = self.WRValues_rst
        self.BLEvalues = self.WRValues_rst
        self.secondsWR = 0
        self.minutesWR = 0
        self.hoursWR = 0
        self.elapsetime = 0
        self.elapsetimeprevious = 0

    def on_rower_event(self, event):
        if event['type'] in IGNORE_LIST:
            return
        if event['type'] == 'stroke_rate':
            self.WRValues.update({'stroke_rate': (event['value']*2)})
        if event['type'] == 'total_strokes':
            self.WRValues.update({'total_strokes': event['value']})
        if event['type'] == 'total_distance_m':
            self.WRValues.update({'total_distance_m': (event['value'])})
        if event['type'] == 'avg_distance_cmps':
            if event['value'] == 0:
                pass
            else:
                InstantaneousPace = (500 * 100) / event['value']
                self.WRValues.update({'instantaneous pace': InstantaneousPace})
        if event['type'] == 'watts':
            self.WRValues.update({'watts': (event['value'])})
        # TODO: Calc the Watt average of 5 stroke in order to have the watts
        if event['type'] == 'total_kcal':
            self.WRValues.update({'total_kcal': (event['value']/1000)})  # in cal now in kcal
        if event['type'] == 'total_kcal_h':  # must calclatre it first
            self.WRValues.update({'total_kcal': 0})
        if event['type'] == 'total_kcal_min':  # must calclatre it first
            self.WRValues.update({'total_kcal': 0})
        if event['type'] == 'heart_rate':
            self.WRValues.update({'heart_rate': 0})  # in cal
        if event['type'] == 'display_sec':
            self.secondsWR = event['value']
        if event['type'] == 'display_min':
            self.minutesWR = event['value']
        if event['type'] == 'display_hr':
            self.hoursWR = event['value']
        self.TimeElapsedcreator()


    def pulse(self,event):
        self.Lastcheckforpulse = int(round(time.time() * 1000))
        if event['type'] == 'pulse':
            self.PulseEventTime = event['at']
            self.rowerreset = False
        self.DeltaPulse = self.Lastcheckforpulse - self.PulseEventTime
        if self.DeltaPulse <= 300:
            self.PaddleTurning = True
        else:
            self.PaddleTurning = False
            self.PulseEventTime = 0
            self.WRvalueStandstill()


    def reset_requested(self,event):
        if event['type'] == 'reset':
            self.rowerreset = True


    def TimeElapsedcreator(self):
        self.elapsetime = datetime.timedelta(seconds=self.secondsWR, minutes=self.minutesWR, hours=self.hoursWR)
        self.elapsetime = int(self.elapsetime.total_seconds())
        if  self.elapsetime >= self.elapsetimeprevious:
        # print('sec:{0};min:{1};hr:{2}'.format(self.secondsWR,self.minutesWR,self.hoursWR))
            self.WRValues.update({'elapsedtime': self.elapsetime})
            self.elapsetimeprevious = self.elapsetime


    def WRvalueStandstill(self):
        self.WRvalue_standstill = self.WRValues_rst
        self.WRvalue_standstill.update({'stroke_rate': 0})
        self.WRvalue_standstill.update({'instantaneous pace': 0})
        self.WRvalue_standstill.update({'watts': 0})


    def SendToBLE(self):
        if self.rowerreset:
            self.BLEvalues = self.WRValues_rst
        elif not self.rowerreset and not self.PaddleTurning:
            self.BLEvalues = self.WRvalue_standstill
        elif not self.rowerreset and self.PaddleTurning:
            self.BLEvalues = self.WRValues
            
    # def SendToANT(self):
    #     if self.rowerreset:
    #         self.ANTvalues = self.WRValues_rst
    #     elif not self.rowerreset and not self.PaddleTurning:
    #         self.ANTvalues = self.WRvalue_standstill
    #     elif not self.rowerreset and self.PaddleTurning:
    #         self.ANTvalues = self.WRValues

def main(in_q, ble_out_q):
    S4 = WaterrowerInterface.Rower()
    S4.open()
    S4.reset_request()
    WRtoBLEANT = DataLogger(S4)
    while True:
        if not in_q.empty():
            ResetRequest_ble = in_q.get()
            print(ResetRequest_ble)
            S4.reset_request()
        else:
            pass
        ble_out_q.append(WRtoBLEANT.BLEvalues)
        #ant_out_q.append(WRtoBLEANT.ANTvalues)
        time.sleep(0.1)

# TODO: check to zerout the elapsed time after a reset. This value stays and is not reset to 0 ? Somewhere there is a bug
# TODO:

# def maintest():
#     S4 = WaterrowerInterface.Rower()
#     S4.open()
#     S4.reset_request()
#     WRtoBLEANT = DataLogger(S4)
#
#     def MainthreadWaterrower():
#         while True:
#         #print(WRtoBLEANT.BLEvalues)
#             #ant_out_q.append(WRtoBLEANT.ANTvalues)
#             #print("Rowering_value  {0}".format(WRtoBLEANT.WRValues))
#             #print("Rowering_value_rst  {0}".format(WRtoBLEANT.WRValues_rst))
#             #print("Rowering_value_standstill  {0}".format(WRtoBLEANT.WRvalue_standstill))
#             print("Reset  {0}".format(WRtoBLEANT.rowerreset))
#             #print("Paddleturning  {0}".format(WRtoBLEANT.PaddleTurning))
#             #print("Lastcheck {0}".format(WRtoBLEANT.Lastcheckforpulse))
#             #print("last pulse {0}".format(WRtoBLEANT.PulseEventTime))
#             #print("is connected {}".format(S4.is_connected()))
#             time.sleep(0.1)
#
#
#     t1 = threading.Thread(target=MainthreadWaterrower)
#     t1.start()
#
#
# if __name__ == '__main__':
#     maintest()