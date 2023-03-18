import gym
#import gymnasium as gym
import panda_gym
from stable_baselines3 import PPO, DDPG, HerReplayBuffer
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import CheckpointCallback
import argparse
import os 
import yaml
from yaml.loader import SafeLoader
from sb3_contrib import TQC
import time
import numpy as np
import torch as th


def train(config, algorithm,env):
    checkpoint_callback = CheckpointCallback(save_freq=config['save_freq'], save_path=config['modelSavePath'],
                                         name_prefix=config['envName']+"_"+config['algorithm']+"_"+config['expNumber'])
    modelDir = config['modelSavePath']
    logDir = config['logSavePath']
    if config['algorithm']=="PPO":
        if config['curriLearning'] ==True:
            model = algorithm.load(modelDir+"/"+config['envName']+""+config['algorithm']+"_"+config['expNumber'], env=env,tensorboard_log= logDir+"/"+config['envName']+"_"+config['algorithm']+"/PPO_"+config['expNumber'])
        else:
            policy_kwargs = dict(activation_fn=th.nn.ReLU, net_arch=[dict(pi=[128, 128], vf=[128,128,])])

            model = algorithm(policy=config['policy'], env=env, n_steps=config['n_steps'],verbose=config['verbose'], batch_size=config['batch_size'], learning_rate=config['learning_rate'],
                              tensorboard_log=logDir+"/"+config['envName']+"_"+config['algorithm'],policy_kwargs=policy_kwargs)
    
    if config['algorithm']=="DDPG":
        model = algorithm(policy=config['policy'], env=env, replay_buffer_class=HerReplayBuffer, verbose=1, 
             gamma=config['gamma'], batch_size=config['batch_size'], buffer_size=config['buffer_size'], learning_rate = 1e-3, replay_buffer_kwargs = config['rb_kwargs'],
             policy_kwargs = config['policy_kwargs'], tensorboard_log=logDir+"/"+config['envName']+""+config['algorithm'])
    
    if config['algorithm']=="TQC":
        
        if config['curriLearning'] ==True:
            model = algorithm.load(modelDir+"/"+config['envName']+""+config['algorithm']+"_"+config['expNumber'], env=env)
            print(f"The loaded_model has {model.replay_buffer.size()} transitions in its buffer")
            model.load_replay_buffer(config['bufferPath']+config['expNumber'])
            #model.set_env(env)
        else:
            model = algorithm(policy=config['policy'], env=env, tensorboard_log=logDir+"/"+config['envName']+"_"+config['algorithm'],
                            verbose=config['verbose'], ent_coef=config['ent_coef'], batch_size=config['batch_size'], gamma=config['gamma'],
                            learning_rate=config['learning_rate'], learning_starts=config['learning_starts'],replay_buffer_class=HerReplayBuffer,
                            replay_buffer_kwargs=config['replay_buffer_kwargs'], policy_kwargs=config['policy_kwargs'])
    
    start_time = time.time()
    #, tb_log_name = logDir+"/"+config['envName']+"_"+config['algorithm']
    if config['curriLearning'] ==True:
        model.learn(total_timesteps=config['total_timesteps'], callback=checkpoint_callback, reset_num_timesteps=False, tb_log_name = logDir+"/"+config['envName']+"_"+config['algorithm']+"/"+config['algorithm'] +"_"+config['curriNumber'])
    else:
        model.learn(total_timesteps=config['total_timesteps'], callback=checkpoint_callback)
    print("Total time:", time.time()-start_time)
    if config['curriLearning'] ==True:
        model.save(modelDir+"/"+config['envName']+""+config['algorithm']+"_"+config['curriNumber'])
    else:
        model.save(modelDir+"/"+config['envName']+""+config['algorithm']+"_"+config['expNumber'])
    
    if config['algorithm']=='TQC':
        if config['curriLearning'] ==True:
            model.save_replay_buffer(config['bufferPath']+config['curriNumber'])   
        else:
            model.save_replay_buffer(config['bufferPath']+config['expNumber'])   

    #del model
    try:
        os.rename(config['logSavePath']+"/"+config['envName']+"_"+config['algorithm']+"/"+config['algorithm']+"_"+config['curriNumber']+"_0", config['logSavePath']+"/"+config['envName']+"_"+config['algorithm']+"/"+config['algorithm']+"_"+config['curriNumber'])
    except FileNotFoundError:
        pass
def load_model(parentDir,config,steps, algorithm,env):
    modelDir = config['modelSavePath']
    if config['curriLearning'] ==True:
        model = algorithm.load(modelDir+"/"+config['envName']+""+config['algorithm']+"_"+config['curriNumber'], env=env) 
    else:
        model = algorithm.load(modelDir+"/"+config['envName']+""+config['algorithm']+"_"+config['expNumber'], env=env) 
    env = model.get_env()
    mae = 0.0
    squaredError = 0.0
    successRate1 = 0.0
    successRate5 = 0.0
    avgJntVel = 0.0
    for step in range(steps):
        print("step:", step)
        counter = 0        
        done = False
        obs = env.reset()
        episode_reward = 0.0
        while not done:
            counter+=1
            action, _states = model.predict(obs, deterministic=True)
            obs, reward, done, info = env.step(action)
            if counter==config['max_episode_steps']-2:
                error = abs(obs['achieved_goal'] - obs['desired_goal'])
                mae = np.linalg.norm(error) + mae
                squaredError += np.sum(error**2)
                avgJntVel = np.linalg.norm(action) + avgJntVel
                if np.linalg.norm(error) <=0.01:
                    successRate1+=1
                
                if np.linalg.norm(error) <=0.05:
                    successRate5+=1
            if done:
                #print("episode done.")
                pass

            episode_reward+=reward
            #env.render()
        #print("episode reward is:", episode_reward)
    #print("Squared Error:",squaredError)
    print("RMSE:", np.sqrt((squaredError)/(steps)))
    print("MAE:", mae/steps)
    print("Success Rate 1 cm:", successRate1/steps)
    print("Success Rate 5 cm:", successRate5/steps)
    print("Average joint velocities:", avgJntVel/steps)
        
        
def main():

    with open('configPPO.yaml') as f:
        config = yaml.load(f, Loader=SafeLoader)

    currentDir = os.getcwd()
    print("number of env:",config['n_envs'])
    if config['algorithm']=="PPO":
        algorithm = PPO
        
    if config['algorithm']=="DDPG":
        algorithm = DDPG

    if config['algorithm']=="TQC":
        algorithm = TQC
    
    env = gym.make(config['envName'], render=config['render'])
    env._max_episode_steps = config['max_episode_steps']
    
    if config['mode'] == True:
        env = make_vec_env('PandaReach-v2', n_envs=config['n_envs']) 
        train(config,algorithm, env)
        env = gym.make(config['envName'], render=config['render'])
        env._max_episode_steps = config['max_episode_steps']
        time.sleep(10)
        load_model(currentDir,config,config['testSamples'], algorithm,env)
    else:
        load_model(currentDir,config,config['testSamples'], algorithm,env)
    print("DONE!!!")
    
if __name__=='__main__':
    main()
    device = th.device('cuda' if th.cuda.is_available() else 'cpu')
    if device.type=='cuda':
        print("number of device",th.cuda.device_count())
        print("current device:",th.cuda.current_device())
        print("device name:",th.cuda.get_device_name())
        print('Allocated:', round(th.cuda.memory_allocated(0)/1024**3,1), 'GB')
        print('Cached:   ', round(th.cuda.memory_reserved(0)/1024**3,1), 'GB')
    
