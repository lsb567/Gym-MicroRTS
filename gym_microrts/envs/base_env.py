import gym
import socket
import numpy as np
import json
from subprocess import Popen, PIPE
import os
from typing import List, Tuple
from dacite import from_dict
from gym_microrts.types import MicrortsMessage, Config
from gym import error, spaces, utils
import xml.etree.ElementTree as ET
from gym.utils import seeding
from PIL import Image
import io
import struct
import mmap

import jpype
from jpype.imports import registerDomain
import jpype.imports
from jpype.types import *

class BaseSingleAgentEnv(gym.Env):
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : 50
    }

    def __init__(self, config=None):
        if config:
            self.init(config)
    
    def init(self, config: Config):
        """
        if `config.microrts_path` is set, then the script will automatically try 
        to launch a microrts client instance. Otherwise you need to set the 
        `config.height` and `config.this script will just wait
        to listen to the microrts client
        """
        self.config = config
        root = ET.parse(os.path.expanduser(self.config.map_path)).getroot()
        self.config.height, self.config.width = int(root.get("height")), int(root.get("width"))
        self.running_first_episode = True
        self.closed = False

        # Launch the JVM
        registerDomain("ts", alias="tests")
        jpype.addClassPath("/home/costa/Documents/work/go/src/github.com/vwxyzjn/microrts/microrts.jar")
        jpype.startJVM()

        from ts import JNIClient
        self.client = JNIClient()
        
        # get the unit type table
        self.utt = json.loads(self.client.sendUTT()) 
        
        # computed properties
        self.init_properties()

    def init_properties(self):
        raise NotImplementedError

    def step(self, action, raw=False):
        action = np.append(action, [self.config.frame_skip])
        action = np.array([action])
        mm = self.client.step(action)
        if raw:
            return convert3DJarrayToNumpy(mm.observation), mm.reward, mm.done, mm.info
        return self._encode_obs(convert3DJarrayToNumpy(mm.observation)), mm.reward, mm.done, mm.info

    def reset(self, raw=False):
        if raw:
            return convert3DJarrayToNumpy(self.client.reset().observation)
        return self._encode_obs(convert3DJarrayToNumpy(self.client.reset().observation))

    def render(self, mode='human'):
        if mode=='human':
            self.client.render(False)
        elif mode == 'rgb_array':
            bytes_array = self.client.render(True)[:]
            image = Image.frombytes("RGB", (640, 640), bytes_array)
            return np.array(image)

    def close(self):
        self.client.close()
    
    def _encode_obs(self, observation: List):
        raise NotImplementedError

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

def convert3DJarrayToNumpy(jArray):
    # get shape
    arr_shape = (len(jArray),)
    temp_array = jArray[0]
    while hasattr(temp_array, '__len__'):
        arr_shape += (len(temp_array),)
        temp_array = temp_array[0]
    arr_type = type(temp_array)
    # transfer data
    resultArray = np.empty(arr_shape, dtype=arr_type)
    for ix in range(arr_shape[0]):
        for i,cols in enumerate(jArray[ix][:]):
            resultArray[ix][i,:] = cols[:]
    return resultArray
