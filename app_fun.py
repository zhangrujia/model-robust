# !/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       :实现GUI各个按钮功能，供app_server调用
@Date               :2023/09/13 16:28
@Author             :Zhang Rujia
@version            :2.0
'''
import os, base64, json, time, requests, cv2, docker, tarfile, math, random, ast, re
import numpy as np
from src.utils.utils import load_config, create_logger
from src.utils.utils import noiseSingleimg, ret_result_image, ret_statistic_img, noiseSingleimg_sec
from src.utils.baseScore import RemoteSensingScore
from operator import itemgetter
from src.utils.imgNoise import img_noise
from skimage.metrics import structural_similarity as ssim

class App_fun():
    
    def __init__(self) -> None:
        """
        @description  :供app_server调用的各项函数
        ---------
        @Returns      :
        -------
        """
        self.cfg = load_config("./config/config.yaml")
        self.logger = create_logger("./log")
        self.path_task = ""
        self.taskId = ""
        self.algorithmNo = None
        self.use_local_model = True
        self.path_model = "./models/detection/yolov5"
        self.use_docker = True
        self.docker_tar = False
        self.model_name = ""
        # self.algorithmNo = False
        
    # 未登录时获取令牌
    def Request_notlog_token (self):
        """
        @description  : 智能测评系统页面未登录，使用accessKey，secretKey获取令牌。
        ---------
        @data_client  :
                accessKey: 公钥	
                secretKey: 私钥
        -------
        @Returns      :
                  code: 状态码
               success: 成功与否
               message: 详细信息
                 data: token值
        -------
        """
        data = {
            "accessKey": self.cfg["ExtNet_para"]["accessKey"],
            "secretKey": self.cfg["ExtNet_para"]["secretKey"]}
        url = self.cfg["url"]["token_url"]
        
        try:
            response = requests.post(url, data = data) 
            json_data = response.json()
            code = json_data["code"]
            success = json_data["success"]
            msg = json_data["message"]
            if success:
                return json_data
            else:
                return {
                    "code": code,
                    "success": success,
                    "message": msg}
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e)}         
   
    # 结果回传
    def Request_SendResult (self): #data_client["taskId"]
        """
        @description  : 智能测评平台将结果回传至训练平台
        ---------
        @data_client  :
                accessKey: 公钥	
                signature: 令牌
                taskId: 任务ID
                source: 平台标识, robust
                file: 需要回传的训练任务报告及文件
        -------
        @Returns      :
                  code: 状态码
               success: 成功与否
               message: 详细信息
                 data: 
        -------
        """
        ret = self.Request_notlog_token()    
        headers = {"accessKey": self.cfg["ExtNet_para"]["accessKey"], "signature":ret["data"]}
        if self.algorithmNo:
            pass  #加结果file
        else:
            if self.taskId:
                print("结果回传taskid：", self.taskId)
                self.logger.info("结果回传taskid：", self.taskId)
                params = {"taskId": self.taskId, "source": "robust"}
            else:
                print("结果回传taskid：", self.taskId)
                self.logger.info("结果回传taskid：", self.taskId)
                params = {"taskId": "f010e2ab-975f-4ab8-8919-7faebd3fca87", "source": "robust"}
            # params = {"taskId": "f010e2ab-975f-4ab8-8919-7faebd3fca87", "source": "robust"}
            #taskId前端传入？
        url = self.cfg["url"]["result_url"]
        if ret["success"]:
            try:
                response = requests.post(url, data = params, headers = headers) 
                json_data = response.json()
                code = json_data["code"]
                success = json_data["success"]
                msg = json_data["message"]
                data = json_data["data"]
                
                if success:
                    return json_data
                else:
                    return {
                        "code": code,
                        "success": success,
                        "message": msg}
            except Exception as e:
                self.logger.error(e)
                return {
                    "success": False,
                    "message": str(e)}             
    
    # 获取用户权限信息
    def request_permission(self, data_client):
        """
        @description  : 获取用户权限信息
        ---------
        @data_client  :
                    id: session id	
                projid: 项目id
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                 token: token值
        -------
        """
        cookie = "MS_SESSION_ID=" + data_client["id"]
        projectid = data_client["projid"]

        headers = {"Cookie": cookie}
        params = {"project": projectid}
        url = self.cfg["url"]["permission_url"]

        try:
            response = requests.get(url, params=json.dumps(params), headers=headers) 
            json_data = response.json()

            success = json_data["success"]
            msg = json_data["message"]
            self.logger.info(msg)

            if success:
                token = json_data["data"]["deploys"][0]["deployToken"]
                return {
                    "success": success,
                    "message": msg,
                    "token": token}
            else:
                return {
                    "success": success,
                    "message": msg}
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e)}

    # 获取文件创建时间
    def get_fileCreateTime(self, filePath):
        timestamp = os.path.getctime(filePath)
        timeStruct = time.localtime(timestamp)
        return time.strftime('%Y-%m-%d %H:%M:%S', timeStruct)

    # 报告回传
    def get_report(self, args):
        """
        @description  : 报告回传
        ---------
        @args         :
            projectId : 项目ID
               taskId : 任务ID
                  page: 分页索引
              pageSize: 分页大小
        -------
        @Returns      :
           ResultsList: 结果列表
                Status: 接口请求状态码
             ItemCount: 总条数
             pageCount: 分页索引
        -------
        """
        ret = {
            "ResultsList": [],
            "Status": 200,
            "ItemCount": 0,
            "pageCount": 0,
            "message": ""
        }
        res = {
            "ID": "",
            "urls": []
        }
        result_list = [] # 存放返回的报告列表
        page, pageSize = int(args["page"]), int(args["pageSize"])
        res["ID"] = args["taskId"]
        
        # path_task = os.path.join(self.cfg["sys_info"]["project_root"], self.cfg["data"]["user_data"], args["projectId"], args["taskId"])
        path_task = os.path.join("/code", self.cfg["data"]["user_data"], args["projectId"], args["taskId"])
        tasks = os.listdir(path_task)
        
        try:
            base_url_port = self.cfg["url"]["permission_url"].split("/")[2]
            base_url = base_url_port.split(':')[0]
            port = self.cfg["web"]["port"]
            
            itemCount = 0
            for t in tasks:
                path_eval = os.path.join(path_task, t, "perform")
                if os.path.exists(path_eval):
                    eval = os.listdir(path_eval)
                    itemCount += len(eval)
                    for e in eval:
                        path_file = os.path.join(path_eval, e, "eval.jpg")
                        result_list.append("http://" + base_url + ":" + str(port) + "/robustness/getPerform?imagepath=" + path_file)
                    
            result_list = sorted(result_list)
            totalPage, remainder = itemCount / pageSize, itemCount % pageSize
            if remainder != 0:
                totalPage += 1
                        
            if page == totalPage:
                result_list = result_list[(page - 1) * pageSize :]
            else:
                result_list = result_list[(page - 1) * pageSize : (page - 1) * pageSize + pageSize]
                    
            res["urls"] = result_list
            ret["ResultsList"].append(res)
            ret["ItemCount"] = itemCount
            ret["pageCount"] = page
            ret["message"] = "success"
        except Exception as e:
            ret["Status"] = 404
            self.logger.error(e)
            ret["message"] = str(e)
            
        return ret

    # 获取子任务信息
    def get_taskInfo(self, args):
        """
        @description  : 返回projectId已创建任务信息
        ---------
        @args         :
             projectId: 项目ID
                taskId: 任务ID
                  page: 分页索引
              pageSize: 分页大小
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 任务信息
        -------
        """
        task_list = [] # 存放返回的任务列表
        page, pageSize = int(args["page"]), int(args["pageSize"])
        path_project = os.path.join("./", self.cfg["data"]["user_data"], args["projectId"], args["taskId"])
        try:
            if not os.path.exists(path_project):
                self._mkdir_path(path_project)
                # print("--NO：返回已创建任务信息，错误信息：不存在对应的projectId或taskId，请检查或首先创建子任务")
                # self.logger.error("ERROR:There is no corresponding projectId or taskId.")
                # return {
                #     "success": False,
                #     "message": "ERROR:There is no corresponding projectId or taskId.",
                #     "data": {
                #         "code": 0 # code为0代表后端不存在相应的projectId和taskId路径，需要检查或创建第一个子任务
                #     }}
            tasks = os.listdir(path_project)
            for t in tasks:
                path_task = os.path.join(path_project, t)
                time = self.get_fileCreateTime(path_task)
                if os.path.exists(os.path.join(path_task, "info.json")):
                    with open(os.path.join(path_task, "info.json"), 'r') as file:
                        data = json.load(file)
                    task_type = data["task_type"]
                    test_type = data["test_type"]
                    task_list.append({'name': t,
                                    'createTime': time,
                                    'taskType': task_type,
                                    'testType': test_type})
                else:
                    self.logger.error("Wrong: Task '" + t + "' is broken!")
                    print("Wrong: Task '" + t + "' doesn't have the info.json!")
            task_list = sorted(task_list, key = lambda i: i['createTime'], reverse=True)

            total = len(task_list)
            totalPage, remainder = total / pageSize, total % pageSize
            if remainder != 0:
                totalPage += 1

            if page == totalPage:
                task_list = task_list[(page - 1) * pageSize :]
            else:
                task_list = task_list[(page - 1) * pageSize : (page - 1) * pageSize + pageSize]
            
            self.logger.info("成功返回已创建任务信息，共"  + str(total) + "个子任务")
            print("--OK：返回已创建任务信息，共"  + str(total) + "个子任务")
            return {
                "success": True,
                "message": "Get '" + path_project + "' task info success",
                "data": {
                    "items": task_list,
                    "total": total,
                    "page": page,
                    "pageSize": pageSize}}
        except Exception as e:
            self.logger.error(e)
            print("--NO：返回已创建任务信息，错误信息：" + str(e))
            return {
                "success": False,
                "message": str(e),
                "data": {
                    "code": 10 # 其他可能的错误
                }}
    
    def is_valid_task_name(self, name):
        # 任务名称长度检查
        if len(name) < 1 or len(name) >= 50:
            return False
        # 检查任务名称是否只包含字母、数字和某些特殊字符，不包含 / 和 \
        if not re.match("^[a-zA-Z0-9!@#$%^&*()_+={}\[\]:;\"'<>,.?-]+$", name):
            return False
        if '/' in name or '\\' in name:
            return False
        return True
    
    def createTask(self, args):
        """
        @description   : 创建新任务
        ---------
        @param         :
            projectId   : 项目ID
            taskId      : 任务ID
            taskName    : 任务名称
        -------
        @Returns       :
                success: 成功与否
                message: 详细信息
        -------
        """
        path_task = os.path.join("./", self.cfg["data"]["user_data"], args["projectId"], args["taskId"], args["taskName"])
        
        if not self.is_valid_task_name(args["taskName"]):
            print("--NO：创建子任务失败，错误信息：任务名{}不符合规则".format(args["taskName"]))
            self.logger.error("ERROR:Task name is wrong.")
            return {
                "success": False,
                "message": "ERROR:Task name is wrong.",
                "data": {
                    "code": 3 # code为3代表任务名不符合规则
            }}
        try:
            # 重复名称检查
            if os.path.exists(path_task):
                print("--NO：创建子任务失败，错误信息：任务名{}重复".format(args["taskName"]))
                self.logger.error("ERROR: Duplicate task name.")
                return {
                    "success": False,
                    "message": "ERROR:Duplicate task name.",
                    "data": {
                        "code": 2 # code为2代表任务名重复
                    }}
            task_json = {
                    "task_type": self.cfg["task_type"][int(args["taskType"])],
                    "test_type": self.cfg["test_type"][int(args["testType"])]}
            os.makedirs(path_task, mode=0o777)
            with open(os.path.join(path_task, "info.json"), "w") as file:
                file.write(json.dumps(task_json))
                
            self.logger.info("成功创建子任务"  + args["taskName"])
            print("--OK：成功创建子任务"  + args["taskName"])
            return {
                "success": True,
                "message": "create taskName:" + args["taskName"] + ", taskId:" + args["taskId"] + ", projectId:" + args["projectId"] + " success"}
        except Exception as e:
            self.logger.error(e)
            print("--NO：创建子任务失败，错误信息：" + str(e))
            return {
                "success": False,
                "message": str(e),
                "data": {
                    "code": 10 # code为10代表其他可能的错误
            }}
    
    # 选择鲁棒性测评子任务
    def setTask(self, path_task, taskId):
        try:
            if os.path.exists(path_task):
                self.path_task = path_task
                self.taskId = taskId
                self.algorithmNo = None
                path_json = os.path.join(path_task, 'info.json')
                # 读取 JSON 文件内容
                with open(path_json, 'r') as f:
                    info = json.load(f)
                key = 'result'
                if key in info:
                    history = True
                else:
                    history = False
                
                test_type = info["test_type"]
                if test_type == "white":
                    self.use_docker = True
                    self.docker_tar = True
                elif test_type == "black":
                    self.use_docker = False
                    self.docker_tar = False
                    self.use_local_model = False
                else:
                    self.logger.error("失败选中子任务，错误信息：测试类型不是白盒或黑盒")
                    print("--NO：失败选中子任务，错误信息：测试类型不是白盒或黑盒")
                    return {
                        "success": False,
                        "message": "测试类型不是白盒或黑盒，创建子任务的信息出错",
                        "data": {
                            "code": 6 # 代表测试类型不是白盒或黑盒，创建子任务的信息出错
                        }}
                
                self.logger.info("成功选中子任务")
                print("--OK：成功选中子任务")
                return {
                    "success": True,
                    "message": "set task '" + path_task + "' success",
                    "data": history}
            else:
                print("--NO：失败选中子任务，错误信息：不存在对应的projectId,taskId或taskName，请检查")
                self.logger.error("ERROR:There is no corresponding projectId, taskId or taskName.")
                return {
                    "success": False,
                    "message": "ERROR:There is no corresponding projectId, taskId or taskName.",
                    "data": {
                    "code": 1 # code为0代表后端不存在相应的projectId,taskId和taskName路径，需要检查
                    }}
        except Exception as e:
            self.logger.error(e)
            print("--NO：失败选中子任务")
            return {
                "success": False,
                "message": str(e),
                "data": {
                        "code": 10 # 代表其他可能的错误
                }}
    
    # 获取数据列表
    def request_datalist(self, args):
        """
        @description     : 发送查询条件到主平台，主平台返回满足条件的数据列表
        ---------
        @args            :
            MS_SESSION_ID: session ID
                projectId: 项目ID
                   prefix: 查询条件
                     page: 分页索引
                 pageSize: 分页大小
        -------
        @Returns         :
                  success: 成功与否
                  message: 详细信息
                     data: 数据列表信息
        -------
        """

        # 获取权限
        permission = {
            "id": args["MS_SESSION_ID"],
            "projid": args["projectId"]}
        ret = self.request_permission(permission)

        # 若权限测试通过
        if ret["success"]:
            
            # 请求获取数据列表
            url = self.cfg['url']['datalist_url']
            params = {"prefix": args["prefix"], "page": args["page"], "pageSize": args["pageSize"]}
            headers = {"Authorization": ret["token"]}
            
            try:
                response = requests.get(url, params=params, headers=headers)
                json_data = response.json()

                code = json_data["code"]
                msg = json_data["message"]
                data = json_data["data"]

                # # 筛选.csv文件
                # items = data["items"]
                # for i, it in enumerate(items):
                #     type = it["name"].split(".")[-1]
                #     if type != "csv":
                #         items.pop(i)
                # data["items"] = items

                self.logger.info(msg)
                
                if code == 200:
                    self.logger.info("成功获取数据列表")
                    print("--OK：成功获取数据列表")
                    return {
                        "success": True,
                        "message": msg,
                        "data": data}
                else:
                    self.logger.error("失败获取数据列表")
                    print("--NO：失败获取数据列表")
                    return {
                        "success": False,
                        "message": msg,
                        "data": {
                            "code": 4 # 代表主平台返回获取数据失败
                        }}
            except Exception as e:
                self.logger.error(e)
                print("--NO：失败获取数据列表")
                return {
                    "success": False,
                    "message": str(e),
                    "data": {
                        "code": 10 # 代表其他可能的错误
                    }}
        
        self.logger.error("失败获取数据列表,错误信息：权限未通过")
        print("--NO：失败获取数据列表,错误信息：权限未通过")
        return {
            "success": False,
            "message": ret["message"],
            "data": {
                "code": 5 # 权限未通过
            }}
        
    # 获取模型列表
    def request_imagelist(self, args):
        """
        @description     : 发送查询条件到主平台，主平台返回满足条件的模型列表
        ---------
        @args            :
            MS_SESSION_ID: session ID
                projectId: 项目ID
                     info: 查询条件
                     page: 分页索引
                 pageSize: 分页大小
        -------
        @Returns         :
                  success: 成功与否
                  message: 详细信息
                     data: 模型列表信息
        -------
        """

        # 获取权限
        permission = {
            "id": args["MS_SESSION_ID"],
            "projid": args["projectId"]}
        ret = self.request_permission(permission)

        # 若权限测试通过
        if ret["success"]:
            
            if os.path.exists(os.path.join(self.path_task, "info.json")):
                with open(os.path.join(self.path_task, "info.json"), 'r') as file:
                    info = json.load(file)
                test_type = info["test_type"]
            else:
                self.logger.error("Wrong: Task is broken!")
                print("Wrong: Task doesn't have the info.json!")

            # 根据测试类型筛选待测模型
            if test_type == "white":
                if args["info"] != '':
                    info = args["info"] + "&.tar"
                else:
                    info = ".tar"
            else:
                if args["info"] != '':
                    info = args["info"] + "&:"
                else:
                    info = ":"
            # print(info)

            # 请求获取数据列表
            url = self.cfg['url']['imagelist_url']
            params = {"info": info, "page": int(args["page"]), "pageSize": int(args["pageSize"])}
            headers = {
                "Authorization": ret["token"],
                'Content-Type': 'application/json'  # 明确指定Content-Type
                }
            
            try:
                response = requests.post(url, data=json.dumps(params), headers=headers)
                json_data = response.json()

                code = json_data["code"]
                msg = json_data["message"]
                data = json_data["data"]

                self.logger.info(msg)
                
                if code == 200:
                    self.logger.info("成功获取模型列表")
                    print("--OK：成功获取模型列表")

                    return {
                        "success": True,
                        "message": msg,
                        "data": data}
                else:
                    self.logger.error("失败获取模型列表")
                    print("--NO：失败获取模型列表")
                    return {
                        "success": False,
                        "message": msg,
                        "data": {
                            "code": 4 # 代表主平台返回获取数据失败
                        }}
            except Exception as e:
                self.logger.error(e)
                print("--NO：失败获取模型列表")
                return {
                    "success": False,
                    "message": str(e),
                    "data": {
                        "code": 10 # 代表其他可能的错误
                    }}
        
        self.logger.error("失败获取模型列表,错误信息：权限未通过")
        print("--NO：失败获取模型列表,错误信息：权限未通过")
        return {
            "success": False,
            "message": ret["message"],
            "data": {
                "code": 5 # 权限未通过
            }}

    # 加载数据
    def request_data(self, data_client):
        """
        @description  : 选择数据列表内的数据，加载对应的数据到本地
        ---------
        @data_client  :
         MS_SESSION_ID: session ID
             projectId: 项目ID
         objectNameArr: 加载数据名称数组
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 加载数据信息
        -------
        """
        # 获取权限
        permission = {
            "id": data_client["MS_SESSION_ID"],
            "projid": data_client["projectId"]}
        ret = self.request_permission(permission)
        
        # 若权限测试通过
        if ret["success"]:
            
            # 请求获取数据
            url = self.cfg["url"]["data_url"]
            headers = {
                "Authorization": ret["token"],
                'Content-Type': 'application/json'  # 明确指定Content-Type
                }
            data = {"objectNameArr": data_client["objectNameArr"]}
            
            try:
                # assert self.path_task != "", "Error: task path is invalid"
                if self.path_task == "":
                    self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
                    print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")

                db_dir = os.path.join(self.path_task, self.cfg["data"]["data_image"])
                self._mkdir_path(db_dir)

                response = requests.post(url, data=json.dumps(data), headers=headers)
                json_data = response.json()
                code = json_data["code"]
                msg = json_data["message"]
                data = json_data["data"]
                self.logger.info(msg)

                if code == 200:
                    
                    total = data["total"]
                    items = data["items"]
                    items = sorted(items, key=itemgetter('name'))
                    
                    k = 0
                    data_samples = os.path.join(self.path_task, self.cfg["data"]["data_image"], "samples")
                    self._mkdir_path(data_samples)
                    
                    gt_path = os.path.join(db_dir, "gt.json")       
                    gt_json = {
                        "input_data_type": "RGB",
                        "output_data_type": "bounding_box",
                        "results":{}}
                    
                    for i in range(total):
                        
                        downloadURL = items[i]['downloadURL']
                        name = items[i]['name']
                        # 加载图片地址.csv
                        data_file = requests.get(downloadURL)
                        path_file = os.path.join(db_dir, name)

                        with open(path_file, 'wb') as file:
                            file.write(data_file.content)
                        
                        # 加载图片
                        with open(path_file, 'r') as file:
                            lines = file.readlines()
                        
                        count = max(len(str(len(lines))), len(str(k)))

                        for line in lines:
                            line = line.strip()
                            line_list = line.split(" ")
                            image_url = line_list[0]
                            bbox = ast.literal_eval(line_list[1])
                            cls = ast.literal_eval(line_list[2])
                            # print("{}, {}, {}".format(image_url, bbox, cls))
                            
                            img_obj = []
                            assert len(bbox) == len(cls), "ERROR: bbox.size != cls.size"
                            for b, c in zip(bbox, cls):
                                bbox_info = {}
                                # if str(c) == '0':
                                #     c = 'b'
                                # elif str(c) == '2':
                                #     c = 'd'
                                bbox_info["class_name"] = str(c)
                                bbox_info["bbox"] = [int(x) for x in b]
                                bbox_info["score"] = 1
                                img_obj.append(bbox_info)
                            
                            type_image = image_url.split(".")[-1]
                            data_image = requests.get(image_url)
                            image_name = "sample_" + str(k).zfill(count) + "." + type_image
                            image_data_samples = os.path.join(data_samples, image_name)

                            k = k + 1
                            
                            with open(image_data_samples, 'wb') as file:
                                file.write(data_image.content)
                                file.close()
                                
                            gt_json["results"][image_name] = img_obj
                            with open(gt_path, "w") as f_result:
                                f_result.write(json.dumps(gt_json))

                    self.logger.info("成功获取数据")
                    print("--OK：成功获取数据")
                    return {
                        "success": True,
                        "message": msg,
                        "data": data}
                else:
                    self.logger.error("失败获取数据")
                    print("--NO：失败获取数据")
                    return {
                        "success": False,
                        "message": msg,
                        "data": {
                            "code": 4 # 代表主平台返回获取数据失败
                        }}
            except Exception as e:
                self.logger.error(e)
                print("--NO：失败获取数据")
                return {
                    "success": False,
                    "message": str(e),
                    "data": {
                        "code": 10 # 代表其他可能的错误
                    }}

        self.logger.error("失败获取数据,错误信息：权限未通过")
        print("--NO：失败获取数据,错误信息：权限未通过")
        return {
            "success": False,
            "message": ret["message"],
            "data": {
                "code": 5 # 权限未通过
            }}
    
    # 加载模型
    def request_image(self, data_client):
        """
        @description  : 选择模型列表内的模型，下载对应的模型到本地
        ---------
        @data_client  :
         MS_SESSION_ID: session ID
             projectId: 项目ID
         objectNameArr: 加载模型名称数组
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 加载模型信息
        -------
        """
        # 获取权限
        permission = {
            "id": data_client["MS_SESSION_ID"],
            "projid": data_client["projectId"]}
        ret = self.request_permission(permission)
        
        # 若权限测试通过
        if ret["success"]:
            
            # 请求获取数据
            url = self.cfg["url"]["data_url"]
            headers = {
                "Authorization": ret["token"],
                'Content-Type': 'application/json'  # 明确指定Content-Type
                }
            data = {"objectNameArr": data_client["objectNameArr"]}

            assert len(data_client["objectNameArr"]) == 1, "Error: 不可以下载多个模型，请选择一个模型进行下载" 
            
            try:

                db_dir = os.path.join(self.path_task, self.cfg["data"]["data_image"])
                self._mkdir_path(db_dir)

                response = requests.post(url, data=json.dumps(data), headers=headers)
                json_data = response.json()
                code = json_data["code"]
                msg = json_data["message"]
                data = json_data["data"]
                self.logger.info(msg)

                if code == 200:
                    
                    total = data["total"]
                    items = data["items"]
                    assert total == 1, "Error: 主平台返回多个下载模型" 
                    
                    for i in range(total):
                        downloadURL = items[i]['downloadURL']
                        name = items[i]['name']
                        # 下载模型地址.tar
                        data_file = requests.get(downloadURL)
                        path_file = os.path.join(db_dir, name)

                        with open(path_file, 'wb') as file:
                            file.write(data_file.content)

                    self.logger.info("成功获取模型")
                    print("--OK：成功获取模型")
                    return {
                        "success": True,
                        "message": msg,
                        "data": data}
                else:
                    self.logger.error("失败获取模型")
                    print("--NO：失败获取模型")
                    return {
                        "success": False,
                        "message": msg,
                        "data": {
                            "code": 4 # 代表主平台返回获取数据失败
                        }}
            except Exception as e:
                self.logger.error(e)
                print("--NO：失败获取模型")
                return {
                    "success": False,
                    "message": str(e),
                    "data": {
                        "code": 10 # 代表其他可能的错误
                    }}

        self.logger.error("失败获取模型,错误信息：权限未通过")
        print("--NO：失败获取模型,错误信息：权限未通过")
        return {
            "success": False,
            "message": ret["message"],
            "data": {
                "code": 5 # 权限未通过
            }}

    # 模型推理
    def model_infer(self, data_path, target_path,  model_name):
        """
        @description  : 模型推理
        ---------
        @data_client  :
             data_path: 输入数据
           target_path: 保存路径
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 推理信息
        -------
        """
        print("name:",model_name)
        result_json = {
            "input_data_type": "RGB",
            "output_data_type": "bounding_box",
            "results":{}}

        # 读取数据
        data_list = os.listdir(data_path)
        data_list = sorted(data_list)

        # 循环推理
        model = model_name.split(":")[0]
        print(self.cfg['detect_port'][model])
        url = self.cfg['url']['detect_url'] + str(self.cfg['detect_port'][model]) + "/detect/" + model_name
        print(url)
        for data_image in data_list:
            # 调用URL接口进行模型推理
            image_path = os.path.join(data_path, data_image)
            # print(image_path)
                
            image_base64 = self.get_image(image_path)
                
            data = {"dataBase64": image_base64}
            try:
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url, headers=headers, data=json.dumps(data))
                json_data = json.loads(response.text)
                
                code = int(json_data["code"])
                msg = json_data["msg"]
                data = json_data["data"]
                self.logger.info(msg)
                    
                if code == 0:
                    # [[61, 45, 200, 211, "class_2", 0.8787]]

                    # 保存到JSON文件
                    img_obj = []
                    for tar in data[0]:
                        bbox_info = {}
                        bbox_info["class_name"] = str(tar[4])
                        bbox_info["bbox"] = [int(tar[0]), int(tar[1]), int(tar[2]), int(tar[3])]
                        bbox_info["score"] = float(tar[5])
                    
                        img_obj.append(bbox_info)
                    # print(img_obj)

                    result_json["results"][data_image] = img_obj
                else:
                    return {
                        "success": False,
                        "message": msg,
                        "data": data}
            except Exception as e:
                self.logger.error(e)
                return {
                    "success": False,
                    "message": str(e),
                    "data": {}}
        
        with open(target_path, "w") as file:
            file.write(json.dumps(result_json))
        
        return {
            "success": True,
            "message": msg,
            "data": target_path}
    
    # 本地模型推理
    def local_infer(self, data_path, target_path):
        """
        @description  : 模型推理
        ---------
        @data_client  :
             data_path: 输入数据
           target_path: 保存路径
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 推理信息
        -------
        """

        try:
            
            data_path = os.path.abspath(data_path)
            ret = self.load_local_model(self.path_model, data_path)
            result_json = self._load_local_json(os.path.join(self.path_model, "result/result.json"))
            
            with open(target_path, "w") as f:
                f.write(json.dumps(result_json))
            
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e),
                "data": {}}
        return {
            "success": True,
            "message": "success",
            "data": target_path}
    
    def load_local_model(self, path_model, data_path):
        self.logger.info("load model path: {}, data path：{}".format(path_model, data_path))
        cmd = "cd {} && python test.py {}".format(path_model, data_path) # && 可以先后执行两条shell命令
        f = os.popen(cmd)
        self.logger.info(f.readlines())
        if os.path.exists(os.path.join(path_model, "result/result.json")):
            self.logger.info("检测到结果文件")
        else:
            self.logger.error("未检测到结果文件")
            return 1
        return 0

    # 生成扰动样本
    def generate_data(self, data_client):
        """
        @description  : 生成扰动样本，并计算每张扰动样本的ssim分数
        ---------
        @data_client  :
             run_type : 添加噪声方式
         interference : 噪声强度
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                 noise: 扰动样本地址
        ssim_score_path: ssim分数json文件地址
        -------
        """

        # 用于测试
        # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov8"
        
        # assert self.path_task != "", "Error: task path is invalid"
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")

        # 创建文件树
        path_basic_data = os.path.join(self.path_task, self.cfg["data"]["data_image"], "samples")
        path_noise_data = os.path.join(self.path_task, self.cfg["data"]["data_noise"])
        self._mkdir_path(path_noise_data)
        path_ssim = os.path.join(self.path_task, self.cfg["data"]["data_noise"],"ssim.json")
        try:
            # 读取原始图片
            image_list = os.listdir(path_basic_data)
            print("----num of image: " + str(len(image_list)))
            self.logger.info("num of image: " + str(len(image_list)))
            ssim_score_dic={}
            # 循环处理图片
            for ii, image_name in enumerate(image_list):
                
                image_path = os.path.join(path_basic_data, image_name)
                image = cv2.imread(image_path)

                # 添加噪声
                if data_client["run_type"] == 0:
                    # 代码添加
                    image_noised, noise_name = self.noiseCode(data_client["code"], image)
                else:
                    # 数值添加
                    #image_noised, noise_name = noiseSingleimg(img=image, interference=data_client["interference"])
                    noise_imgdic, noise_intensitydic = noiseSingleimg_sec(img=image, interference=data_client["interference"])
                
                #目前只写了数值添加
                if ii == 0:
                    print("添加噪声强度：" + str(noise_intensitydic["allnoise"]))
                ssim_score_dic_perimg={}
                for key,value in noise_intensitydic.items():
                    for k in range(len(value)):
                        noise_path = os.path.join(path_noise_data, value[k])
                        if ii == 0:
                            # 检查历史噪声工况，避免重复执行
                            if os.path.exists(noise_path):
                                self.logger.info("存在历史噪声工况" + value[k])
                                print("存在历史噪声工况" + str(value[k]))
                                continue
                            else:
                                self._mkdir_path(noise_path)
                        cv2.imwrite(os.path.join(noise_path, image_name), noise_imgdic[key][k]) 
                        if key != "allnoise":
                            if k ==  len(value) - 1:
                                image1 = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                                image2 = cv2.cvtColor(noise_imgdic[key][k], cv2.COLOR_BGR2GRAY)
                                ssim_score = ssim(image1, image2)
                                ssim_score_dic_perimg[key]=ssim_score
                ssim_score_dic[image_name]=ssim_score_dic_perimg
    
                '''
                # 创建噪声文件夹
                if i == 0:
                    noise_path = os.path.join(path_noise_data, noise_name)
                    # 检查历史噪声工况，避免重复执行
                    if os.path.exists(noise_path):
                        self.logger.info("存在历史噪声工况" + noise_name)
                        return {
                            "success": True,
                            "message": "there exists the history data.",
                            "data": noise_name}
                    else:
                        self._mkdir_path(noise_path)
                
                cv2.imwrite(os.path.join(noise_path, image_name), image_noised)
                '''
            with open(path_ssim, "w") as file:
                file.write(json.dumps(ssim_score_dic))
            
        except Exception as e:
                self.logger.error(e)
                print("--NO：失败添加噪声")
                return {
                    "success": False,
                    "message": str(e),
                    "data": {
                        "code": 10 # 代表其他可能的错误
                    }}

        self.logger.info("成功添加噪声")
        print("--OK：成功添加噪声")
        return {
            "success": True,
            "message": "success",
            "noise": noise_intensitydic,
            "ssim_score_path": path_ssim
            }

    # 预设工况生成扰动样本
    def pre_conditions(self, conditionId):
        """
        @description  : 生成扰动样本，并计算每张扰动样本的ssim分数
        ---------
        @data_client  :
           conditionId: 调用工况序号
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                 noise: 扰动样本地址
       ssim_score_path: ssim分数json文件地址
        -------
        """

        # 用于测试
        # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov8"
        
        # assert self.path_task != "", "Error: task path is invalid"
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")

        # 创建文件树
        path_basic_data = os.path.join(self.path_task, self.cfg["data"]["data_image"], "samples")
        path_noise_data = os.path.join(self.path_task, self.cfg["data"]["data_noise"])
        self._mkdir_path(path_noise_data)
        path_ssim = os.path.join(self.path_task, self.cfg["data"]["data_noise"],"ssim.json")
        try:
            # 读取原始图片
            image_list = os.listdir(path_basic_data)
            self.logger.info("num of image: " + str(len(image_list)))
            ssim_score_dic={}
            # 循环处理图片
            for ii, image_name in enumerate(image_list):
                
                image_path = os.path.join(path_basic_data, image_name)
                image = cv2.imread(image_path)

                # 预设工况添加噪声
                pre_interference = self.cfg["preConditions"][int(conditionId)]["interference"]
                # print(pre_interference)
                noise_imgdic, noise_intensitydic = noiseSingleimg_sec(img=image, interference=pre_interference)
                
                #目前只写了数值添加
                if ii == 0:
                    print("添加噪声强度：" + str(noise_intensitydic["allnoise"]))
                ssim_score_dic_perimg={}
                for key,value in noise_intensitydic.items():
                    for k in range(len(value)):
                        noise_path = os.path.join(path_noise_data, value[k])
                        if ii == 0:
                            # 检查历史噪声工况，避免重复执行
                            if os.path.exists(noise_path):
                                self.logger.info("存在历史噪声工况" + value[k])
                                print("存在历史噪声工况" + str(value[k]))
                                continue
                            else:
                                self._mkdir_path(noise_path)
                        cv2.imwrite(os.path.join(noise_path, image_name), noise_imgdic[key][k]) 
                        if key != "allnoise":
                            if k ==  len(value) - 1:
                                image1 = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                                image2 = cv2.cvtColor(noise_imgdic[key][k], cv2.COLOR_BGR2GRAY)
                                ssim_score = ssim(image1, image2)
                                ssim_score_dic_perimg[key]=ssim_score
                ssim_score_dic[image_name]=ssim_score_dic_perimg
    
                '''
                # 创建噪声文件夹
                if i == 0:
                    noise_path = os.path.join(path_noise_data, noise_name)
                    # 检查历史噪声工况，避免重复执行
                    if os.path.exists(noise_path):
                        self.logger.info("存在历史噪声工况" + noise_name)
                        return {
                            "success": True,
                            "message": "there exists the history data.",
                            "data": noise_name}
                    else:
                        self._mkdir_path(noise_path)
                
                cv2.imwrite(os.path.join(noise_path, image_name), image_noised)
                '''
            with open(path_ssim, "w") as file:
                file.write(json.dumps(ssim_score_dic))
            
        except Exception as e:
                self.logger.error(e)
                print("--NO：失败添加噪声")
                return {
                    "success": False,
                    "message": str(e),
                    "data": {
                        "code": 10 # 代表其他可能的错误
                    }}

        self.logger.info("成功预设工况添加噪声")
        print("--OK：成功添加噪声")
        return {
            "success": True,
            "message": "success",
            "noise": noise_intensitydic,
            "ssim_score_path": path_ssim
            }

    # 代码添加噪声
    def noiseCode(self, code, image):
        """
        @description  : 代码添加噪声
        ---------
        @params       :
                 code : 代码
                image : 图片
        -------
        @Returns      :
          image_noised: 噪声图片
            noise_name: 噪声强度名
        -------
        """
        # 代码添加
        noiseImg = img_noise(image)

        # 创建一个字典，其中包含要传递给 exec() 的对象
        exec_globals = {'noiseImg': noiseImg}
        exec(code, exec_globals)

        noiseImg = exec_globals['noiseImg']
        image_noised = noiseImg.img
        noise_name = "".join(noiseImg.intensity)

        return image_noised, noise_name

    def request_historylist(self):
        """
        @description     : 发送查询条件到主平台，主平台返回满足条件的模型列表
        ---------
        @Returns         :
                  success: 成功与否
                  message: 详细信息
                     data: 模型列表信息
        -------
        """
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")
        
        path_json = os.path.join(self.path_task, 'info.json')
        # 读取 JSON 文件内容
        with open(path_json, 'r') as f:
            info = json.load(f)

        try:
            history = info['result']
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e),
                "data": {}}
        
        return {
            "success": True,
            "message": "success",
            "data": history}

    # 噪声样本测试结果
    def ret_result(self, data_client):
        """
        @description  : 噪声样本测试结果
        ---------
        @data_client  :
            noise_name: 噪声强度名
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 生成信息
        -------
        """
        # 用于测试
        # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov8"
        
        # assert self.path_task != "", "Error: task path is invalid"
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")
        noise_name = data_client["noise_name"]
        
        # 创建文件树
        # path_basic_data = os.path.join(self.path_task, self.cfg["data"]["data_image"], "ori_result")
        path_noise_data = os.path.join(self.path_task, self.cfg["data"]["data_noise"], noise_name)
        path_result_data = os.path.join(self.path_task, self.cfg["data"]["data_result"])
        self._mkdir_path(path_result_data)
        
        # with open(os.path.join(self.path_task, "info.json"), 'r') as file:
        #         data = json.load(file)
        # test_type = data["test_type"]
        # if test_type == "white":
        #     self.use_docker = True
        # elif test_type == "black":
        #     self.use_docker = False
        #     self.use_local_model = False
        
        try:
            result_path = os.path.join(path_result_data, noise_name)
            # 检查历史工况，避免重复执行
            if os.path.exists(result_path):
                self.logger.info("存在历史噪声测试结果: " + noise_name)
                return {
                    "success": True,
                    "message": "there exists the history result.",
                    "data": {}}
            else:
                
                # ------------------------------------------------------------
                if not os.path.exists(path_noise_data):
                    return {
                        "success": False,
                        "message": "No corresponding noise data.",
                        "data": {}}
                    
                # 模型推理
                json_path = os.path.join(path_result_data, noise_name + ".json")
                if self.use_docker:
                    res = self.run_docker_image(path_noise_data, json_path)
                else:
                    if self.use_local_model:
                        res = self.local_infer(path_noise_data, json_path)
                    else:
                        res = self.model_infer(path_noise_data, json_path, self.model_name)
                
                self._mkdir_path(result_path)
                
                with open(json_path, 'r') as file:
                    data = json.load(file)
                
                for key, value in data["results"].items():
                    image = cv2.imread(os.path.join(path_noise_data, key))
                    image_result = ret_result_image(value, image)
                    cv2.imwrite(os.path.join(result_path, key), image_result)
                    
                # ------------------------------------------------------------

        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e),
                "data": {}}
        
        
        path_json = os.path.join(self.path_task, 'info.json')
        # 读取 JSON 文件内容
        with open(path_json, 'r') as f:
            info = json.load(f)

        # 如果键存在，则追加列表元素；如果不存在，则创建新的键并填入列表元素
        key = 'result'
        if key in info:
            info[key].append(noise_name)
        else:
            info[key] = [noise_name]

        # 写入 JSON 文件
        with open(path_json, 'w') as f:
            json.dump(info, f, indent=4)  # indent 参数用于指定缩进空格数，使得输出的 JSON 文件更易读
        
        return {
            "success": True,
            "message": "success",
            "data": {}}
    
    '''
    @Author: Wang Sitong
    @Date: 2024/07/20
    @Description: 二级指标开发
    ''' 
    #二级指标 噪声样本推理
    def ret_sec_score_result(self, data_client):
            """
            @description  : 对噪声样本进行推理，推理结果写入json文件
            ---------
            @data_client  :
                noise_name_list: 噪声强度名列表
            -------
            @Returns      :
                success: 成功与否
                message: 详细信息
                    data: 生成信息
            -------
            """
            # 用于测试
            # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov8"
            
            # assert self.path_task != "", "Error: task path is invalid"
            if self.path_task == "":
                self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
                print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")
            noise_name_dic = data_client["noise"]
            
            # 创建文件树
            for key, value in noise_name_dic.items():
                for noise_name in value:
            #for j in range(len(noise_name_list)):
                #for k in range(len(noise_name_list[j])):
                    path_noise_data = os.path.join(self.path_task, self.cfg["data"]["data_noise"], noise_name)
                    path_result_data = os.path.join(self.path_task, self.cfg["data"]["data_result"])
                    self._mkdir_path(path_result_data)
            
                    try:
                        result_path = os.path.join(path_result_data, noise_name)
                        # 检查历史工况，避免重复执行
                        if os.path.exists(result_path):
                            self.logger.info("存在历史噪声测试结果: " + noise_name)
                            print("存在历史噪声测试结果: " + noise_name)
                        else:
                            if not os.path.exists(path_noise_data):
                                self.logger.error("失败生成用于计算二级指标的中间文件,没有对应强度的噪声添加文件")
                                print("--NO：失败生成用于计算二级指标的中间文件,没有对应强度的噪声添加文件")
                                return {
                                    "success": False,
                                    "message": "No corresponding noise data.",
                                    "data": {
                                        "code": 7 # 代表生成用于计算二级指标的中间文件时,没有对应强度的噪声添加文件
                                    }}
                                
                            # 模型推理
                            json_path = os.path.join(path_result_data, noise_name + ".json")
                            
                            if self.use_docker:
                                res = self.run_docker_image(path_noise_data, json_path)
                            else:
                                if self.use_local_model:
                                    res = self.local_infer(path_noise_data, json_path)
                                else:
                                    res = self.model_infer(path_noise_data, json_path, self.model_name)
                            
                            self._mkdir_path(result_path)
                            
                            with open(json_path, 'r') as file:
                                data = json.load(file)
                            
                            for key_, value_ in data["results"].items():
                                image = cv2.imread(os.path.join(path_noise_data, key_))
                                image_result = ret_result_image(value_, image)
                                cv2.imwrite(os.path.join(result_path, key_), image_result)
                                

                    except Exception as e:
                        self.logger.error(e)
                        print("--NO：失败生成用于计算二级指标的中间文件")
                        return {
                            "success": False,
                            "message": str(e),
                            "data": {
                                "code": 10 # 代表其他可能的错误
                            }}
                    
                    
                    # path_json = os.path.join(self.path_task, 'info.json')
                    # # 读取 JSON 文件内容
                    # with open(path_json, 'r') as f:
                    #     info = json.load(f)

                    # # 如果键存在，则追加列表元素；如果不存在，则创建新的键并填入列表元素
                    # key = 'result'
                    # if key in info:
                    #     if noise_name in info[key]:
                    #         pass
                    #     else:
                    #         info[key].append(noise_name)
                    # else:
                    #     info[key] = [noise_name]

                    # # 写入 JSON 文件
                    # with open(path_json, 'w') as f:
                    #     json.dump(info, f, indent=4)  # indent 参数用于指定缩进空格数，使得输出的 JSON 文件更易读
             
            path_json = os.path.join(self.path_task, 'info.json')
            # 读取 JSON 文件内容
            with open(path_json, 'r') as f:
                info = json.load(f)

            # 如果键存在，则追加列表元素；如果不存在，则创建新的键并填入列表元素
            key = 'result'
            history_noise = noise_name_dic["allnoise"][0]
            # print(history_noise)
            if key in info:
                if history_noise in info[key]:
                    pass
                else:
                    info[key].append(history_noise)
            else:
                info[key] = [history_noise]

            # 写入 JSON 文件
            with open(path_json, 'w') as f:
                json.dump(info, f, indent=4)  # indent 参数用于指定缩进空格数，使得输出的 JSON 文件更易读
                   
            self.logger.info("成功生成用于计算二级指标的中间文件")
            print("--OK：成功生成用于计算二级指标的中间文件")
            return {
                "success": True,
                "message": "success",
                    "data": {}}
    
    '''
    @Author: Wang Sitong
    @Date: 2024/09/03
    @Description: 噪声推理结果图展示
    ''' 
    def ret_noise_img(self,noise_name):
        """
        @description  : 返回五张噪声推理结果图
        ---------
        @data_client  :
            noise_name: 噪声强度名
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
              img_list: 五张噪声推理结果图
        -------
        """
        path_img_list = os.path.join(self.path_task, self.cfg["data"]["data_result"], noise_name)
        noise_img_files = os.listdir(path_img_list)
        img_list = []
        #print(noise_img_files)
        if len(noise_img_files)>5: #抽取五张
            noise_img_files = random.sample(noise_img_files,5)
        #print(noise_img_files)
        try:
            for img in noise_img_files:
                path_img = os.path.join(path_img_list,img)
                image_noise = self.get_image(path_img)
                img_list.append(image_noise)
            return{
                    "success": True,
                    "message": "success",
                   "img_list": img_list}
        except Exception as e:
            self.logger.error(e)
            print("--NO：失败读取噪声推理结果图")
            return {
                "success": False,
                "message": str(e),
                "data": {
                #"code": 10 # 代表其他可能的错误
                }}

        
    
    '''
    @Author: Wang Sitong
    @Date: 2024/07/22
    @Description: 一级指标开发
    ''' 
    def ret_SSIM_score(self):
        """
            @description  : 输入每张图中每类噪声的ssim分数json文件，对所有图片的ssim分数求均值
            ---------
            @Returns      :
                  ssim_dic: 每类噪声的ssim分数均值
            -------
        """
        path_ssim = os.path.join(self.path_task, self.cfg["data"]["data_noise"],"ssim.json")
        with open(path_ssim, 'r') as f:
            info = json.load(f)
        first_key = next(iter(info))
        ssim_dic={}
        for noise_name in info[first_key]:
            ssim_dic[noise_name]=[]
        for img_name in info:
            value_dic = info[img_name]
            for key_,value_ in value_dic.items():
                for noise_name in ssim_dic:
                    if key_ == noise_name:
                        ssim_dic[noise_name].append(value_)
        print(ssim_dic)
        for noise_name, score_list in ssim_dic.items():
            ssim_dic[noise_name]=sum(score_list)/len(score_list)
        return {
            "ssim_dic": ssim_dic
        }
        
    def ret_fst_score(self, data_client):
        """
            @description  : 输入ssim分数和二级指标分数，计算一级指标分数
            ---------
            @data_client  :
             score_sec_dic: 二级指标分数
                  ssim_dic: ssim分数
            ---------
            @Returns      :
                 score_fst: 一级指标分数
            -------
        """    
        ssim_dic = data_client["ssim_dic"]
        score_sec_dic = data_client["score_sec_dic"]
        sum_value = 0.0
        score_fst = 0.0
        first_key = next(iter(ssim_dic))
        max_value = -(ssim_dic[first_key])
        try:
            for key, value in ssim_dic.items():
                ssim_dic[key] = -value
                if -value > max_value:
                    max_value = -value
            print(" max_value:", max_value)
            for key, value in ssim_dic.items():
                ssim_dic[key] = math.exp(value-max_value)
                sum_value = ssim_dic[key] + sum_value
            print("ssim_dic:",ssim_dic)
            print("sum_value:",sum_value)
            for key, value in ssim_dic.items():
                ssim_dic[key] = value/sum_value
                for key_, value_ in score_sec_dic.items():
                    if key == key_:
                        score_fst = score_fst + value_ * ssim_dic[key]
            print("ssim_dic:",ssim_dic)
            print("score_fst:",score_fst)
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e),
                "score_fst": {}}
        return {
            "success": True,
            "message": "success",
            "score_fst": score_fst
            }
    
    def get_noise(self, args):
        """
        @description  : 噪声样本测试结果
        ---------
        @data_client  :
            noise_name: 噪声强度名
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 生成信息
        -------
        """
        noise_name = args["noise_name"]
        # 将每个数字转换为列表
        intensity = [int(char) for char in noise_name]
        res = {
            "compression": {
                "intensity":intensity[16],
                "weight":1},
            "pixelate": {
                "intensity":intensity[0],
                "weight":1},
            "zoom": {
                "intensity":intensity[1],
                "weight":1},
            "pulse": {
                "intensity":intensity[2],
                "weight":1},
            "bright": {
                "intensity":intensity[3],
                "weight":1},
            "spatter": {
                "intensity":intensity[4],
                "weight":1},
            "gaussianblur": {
                "intensity":intensity[5],
                "weight":1},
            "affine": {
                "intensity":intensity[6],
                "weight":1},
            "saturate": {
                "intensity":intensity[7],
                "weight":1},
            "fog": {
                "intensity":intensity[8],
                "weight":1},
            "motionblur": {
                "intensity":intensity[9],
                "weight":1},
            "defocusblur": {
                "intensity":intensity[10],
                "weight":1},
            "fastsnow": {
                "intensity":intensity[11],
                "weight":1},
            "dropout": {
                "intensity":intensity[12],
                "weight":1},
            "gaussiannoise": {
                "intensity":intensity[13],
                "weight":1},
            "coarse": {
                "intensity":intensity[14],
                "weight":1},
            "snow": {
                "intensity":intensity[15],
                "weight":1}      
        }
        return res
    
    def get_preConName(self, conditionId):
        """
        @description  : 返回预设工况名称
        ---------
        @data_client  :
           conditionId: 预设工况序号
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 预设工况名称信息
        -------
        """
        try:
            conditionName = self.cfg["preConditions"][int(conditionId)]["conditionName"]
            return {
                "success": True,
                "message": "Get Name Success.",
                "data": conditionName}
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e),
                "data": {}}
    
    def _mkdir_path(self, path_dir):
        if not os.path.exists(path_dir):
            os.makedirs(path_dir, mode=0o777)
            # print("creat " + path_dir + " success")
        # else:
            # print("dir " + path_dir + " exists")

    def ret_result_image(self, index, noise_name):
        """
        @description  : 噪声样本测试结果
        ---------
        @params       : 
                 index: 测试图片序号
            noise_name: 噪声强度名
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 生成信息
        -------
        """
        # 用于测试
        # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov8"
        
        # assert self.path_task != "", "Error: task path is invalid"
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")

        # 噪声图片
        path_noise_data = os.path.join(self.path_task, self.cfg["data"]["data_noise"], noise_name)
        if not 0 <= index < len(os.listdir(path_noise_data)):
            print("index is not allowed, make it 0")
            index = 0
        image_noise_path = os.path.join(path_noise_data, sorted(os.listdir(path_noise_data))[index])
        # print(image_noise_path)

        # 原始图片
        data_samples = os.path.join(self.path_task, self.cfg["data"]["data_image"], "samples")
        image_org_path = os.path.join(data_samples, sorted(os.listdir(data_samples))[index])
        # print(image_org_path)

        # 测试结果图片
        path_result_data = os.path.join(self.path_task, self.cfg["data"]["data_result"], noise_name)
        image_result_path = os.path.join(path_result_data, sorted(os.listdir(path_result_data))[index])
        # print(image_result_path)

        # 原图推理结果
        data_results = os.path.join(self.path_task, self.cfg["data"]["data_image"], "results")
        org_image_result_path = os.path.join(data_results, sorted(os.listdir(data_results))[index])
        # print(org_image_result_path)

        try:
            image_noise = self.get_image(image_noise_path)
            org_image_result = self.get_image(org_image_result_path)
            image_org = self.get_image(image_org_path)
            image_result = self.get_image(image_result_path)
            
            self.logger.info("成功返回示例结果图片")
            print("--OK：成功返回示例结果图片")
            return {
                "success": True,
                "message": "success",
                "data": {
                    "org": image_org,
                    "org_result": org_image_result,
                    "noise": image_noise,
                    "result": image_result}}
        except Exception as e:
            self.logger.error(e)
            print("--NO：失败返回示例结果图片")
            return {
                "success": False,
                "message": str(e),
                "data": {
                    "code": 10 # 其他错误信息
                }}
    
    def get_image(self, image_path):
        image = cv2.imread(image_path)
        _, image_encode = cv2.imencode('.jpg', image)
        image_base64_byte  = image_encode.tobytes()
        image_base64 = base64.b64encode(image_base64_byte).decode()
        return image_base64

    def _load_local_json(self, path_json):
        with open(path_json, "r") as f:
            ret = json.load(f)
        f.close()
        return ret

    def ret_third_score(self, noise_name):
        """
        @description  : 返回三级指标分数
        ---------
        @data_client  :
            noise_name: 噪声强度名
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
           third_score: 三级指标分数
        -------
        """
        # 用于测试
        # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov5"
        
        # assert self.path_task != "", "Error: task path is invalid"
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")

        # 进行结果性能评估
        score_info = []
        score_dic={}
        path_result = os.path.join(self.path_task, self.cfg["data"]["data_result"], noise_name  + ".json")
        path_label = os.path.join(self.path_task, self.cfg["data"]["data_image"], "label.json")
        path_gt = os.path.join(self.path_task, self.cfg["data"]["data_image"], "gt.json")
        # path_perform = os.path.join(self.path_task, self.cfg["data"]["data_perform"], noise_name)
        # self._mkdir_path(path_perform)
        
        random_lab_path = os.path.join(self.path_task, self.cfg["data"]["data_image"], "random_label.json")         
        # with open(path_label, 'r', encoding='utf-8') as f:
        #     lab_label = json.load(f)
        with open(path_gt, 'r', encoding='utf-8') as f:
            gt_label = json.load(f)
            
        with open(os.path.join(self.path_task, "info.json"), 'r') as ff:
            info = json.load(ff)
        key_ = 'third_score'
        # 如果键存在，则读取列表元素；如果不存在，则创建新的键并填入列表元素
        if key_ in info and info[key_].get(noise_name,0) != 0:
            score_info = info[key_][noise_name]
        else:
            if key_ not in info:
                info[key_]={}
            info[key_][noise_name]=[]
            #每次抽样本的80%，计算三次求平均
            for i in range(3):
                random_lab={}
                #随机抽80%写入临时json
                random_key = random.sample(gt_label['results'].keys(), int(0.5*len(gt_label['results'])))
                print("random_key:",random_key)
                for key in random_key:
                    random_lab[key]=gt_label['results'][key]
                new_data = {"input_data_type": "RGB", "output_data_type": "bounding_box", "results": random_lab}
                with open(random_lab_path, 'w') as f:
                    json.dump(new_data, f, indent=4)
                try:
                    ret_json1 = self.calculator_basic_remote_sensing(path_label, random_lab_path) # 真值和加噪前
                    ret_json2 = self.calculator_basic_remote_sensing(path_result, random_lab_path) # 真值和加噪后
                    print("真值和加噪前" + str(ret_json1))
                    print("真值和加噪后" + str(ret_json2))
                    score_info.append({
                        "gt_prenoise": ret_json1,
                        "gt_afternoise": ret_json2
                        })
                except Exception as e:
                    self.logger.error(e)
                    print("--NO：失败计算三级指标")
                    return {
                        "success": False,
                        "message": str(e),
                        "data": {
                                "code": 10 # 代表其他可能的错误
                        }}
            info[key_][noise_name] = score_info
            with open(os.path.join(self.path_task, "info.json"), 'w') as f:
                json.dump(info, f, indent=4)  

        
        # score_dic={}
        # print("third_score=",score_info)
        '''
        for key,value in score_info[0].items():
            score_dic[key]=0.0
        for score_ in score_info:
            for key,value in score_.items():
                score_dic[key] = value/3 + score_dic[key] #三次求平均
        image_eval = ret_statistic_img(score_dic, path_perform)
        '''
        self.logger.info("成功计算三级指标")
        print("--OK：成功计算三级指标")
        return {
            "success": True,
            "message": "success",
            "third_score": score_info
        }

    def calculator_basic_remote_sensing(self, path_result, path_label) -> dict:
        ret_json = {}
        calculator = RemoteSensingScore(path_result, path_label)
        ret = calculator.ret_result()
        ret_json = self.flash_ret(ret_json, ret)
        return ret_json
    
    def flash_ret(self, ret_json, result):
        for key_result, content in result.items():
            ret_json[key_result] = content
        return ret_json
    
    '''
    @Author: Wang Sitong
    @Date: 2024/07/20
    @Description: 二级指标开发
    ''' 
    def ret_sec_score(self, data_client):
        '''
            @description: 传入加噪列表，返回二级指标分数
            ---------
            @data_client:
                noise_name_list: 二维加噪列表
                                [noiseImg_intensitylist1,noiseImg_intensitylist2]
            ---------
            @Returns: 
                score_sec:      二级指标分数
        '''
        noise_name_dic = data_client["noise"]
        score_dic = {}
        score_sec_dic1 = {}
        score_sec_dic2 = {}
        score_sec_dic3 = {}
        score_sec_perlevel_dic1 = {}
        score_sec_perlevel_dic2 = {}
        score_sec_perlevel_dic3 = {}
        score_sec_list=[score_sec_dic1,score_sec_dic2,score_sec_dic3]
        score_sec_perlevel_list=[score_sec_perlevel_dic1,score_sec_perlevel_dic2,score_sec_perlevel_dic3]
        path_label = os.path.join(self.path_task, self.cfg["data"]["data_image"], "label.json")
        random_lab_path = os.path.join(self.path_task, self.cfg["data"]["data_image"], "random_label.json")
        with open(path_label, 'r', encoding='utf-8') as f:
            lab_label = json.load(f)
        if "allnoise" in noise_name_dic:
            noise_name_ = noise_name_dic["allnoise"][0]
            del noise_name_dic["allnoise"]
        for key, value in noise_name_dic.items():
            if value[-1] != '00000000000000000':
                print("----" + str(key) + ": " + str(value[-1]))
            del value[-1]
        
        with open(os.path.join(self.path_task, "info.json"), 'r') as ff:
            info = json.load(ff)
        key_ = 'second_score'
        # 如果键存在，则读取列表元素；如果不存在，则创建新的键并填入列表元素
        if key_ in info and info[key_].get(noise_name_,0) != 0:
            score_sec_perlevel_list = info[key_][noise_name_]
        else:
            if key_ not in info:
                info[key_]={}
            info[key_][noise_name_]=[]
        
            #计算三次取平均
            for i in range(3):
                random_lab={}
                #随机抽50%写入临时json
                random_key = random.sample(lab_label['results'].keys(), int(0.5*len(lab_label['results'])))
                # print("random_key:",random_key)
                for _key_ in random_key:
                    random_lab[_key_]=lab_label['results'][_key_]
                new_data = {"input_data_type": "RGB", "output_data_type": "bounding_box", "results": random_lab}
                with open(random_lab_path, 'w') as f:
                    json.dump(new_data, f, indent=4)
                for key, value in noise_name_dic.items():
                    if value[0] == '00000000000000000':
                        continue
                    else:
                        score_sec = 0             
                        score_noise_img_list = []
                        for noise_name in value:
                            path_result = os.path.join(self.path_task, self.cfg["data"]["data_result"], noise_name  + ".json") 
                            try:
                                calculator = RemoteSensingScore(path_result, random_lab_path)
                                per_img_map = float(calculator.mAP())
                                score_noise_img_list.append(per_img_map)
                            except Exception as e:
                                self.logger.error(e)
                                print("--NO：失败计算二级指标")
                                return {
                                    "success": False,
                                    "message": str(e),
                                    "data": {
                                        "code": 10 # 代表其他可能的错误
                                    }}
                        # print("map_list:",score_noise_img_list)             
                        score_sec = sum(score_noise_img_list)/len(score_noise_img_list)
                        score_sec_perlevel_list[i][key] = score_noise_img_list
                        score_sec_list[i][key] = score_sec

            info[key_][noise_name_] = score_sec_perlevel_list
            with open(os.path.join(self.path_task, "info.json"), 'w') as f:
                json.dump(info, f, indent=4)
                
        print(noise_name_)
        '''
        score_dic[noise_name_] = score_sec_perlevel_list

        with open(os.path.join(self.path_task, "info.json"), 'r') as f:
            info = json.load(f)
        key = 'second_score'
        # 如果键存在，则追加列表元素；如果不存在，则创建新的键并填入列表元素
        if key in info:
            if info[key].get(noise_name_) is not None:
                info[key][noise_name_] = score_sec_perlevel_list
            else:
                info[key].update(score_dic)
        else:
            info[key] = score_dic
        # 写入 JSON 文件
        with open(os.path.join(self.path_task, "info.json"), 'w') as f:
            json.dump(info, f, indent=4)
        '''
        self.logger.info("成功计算二级指标")
        print("--OK：成功计算二级指标")       
        return {
                "success": True,
                "message": "success",
                "noise_name_dic": noise_name_dic,
                "sec_score": score_sec_perlevel_list,
                "score_sec_list": score_sec_list
            }


    def run_docker_image(self, data_samples, result_path):
        """
        @description  : 完成加载docker后，在容器中运行被测算法
        ---------
        @path_data    : 传送给被测算法的，数据集路径
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 
        -------
        """
        print("Using docker.......")
        try:
            data_samples = data_samples.split("/db")[-1]
            cmd = ["python", "test.py", "/data" + data_samples]
            print(cmd)
            code, stream = self.docker_container.exec_run(cmd, stream=True)  # 返回一个元祖 (exit_code, output)   stream就是我们的命令的输出的返回值,但是需要decode一下
            s = ''   
            for x in stream:
                s += x.decode()
            print(s)
            self.get_files("/result/result.json", result_path)
        except Exception as e:
            self.logger.error(e)
            return {
                "success": False,
                "message": str(e),
                "data": {}}
        return {
            "success": True,
            "message": "success",
            "data": s}
    
    def get_files(self, path_file_inDocker, path_file_Local):
        """
        @description         : 将docker中的文件复制到宿主机中
        ---------
        @path_file_inDocker  : docker中的路径，必须是容器中的绝对路径
        @path_file_Local     : 宿主机路径
        -------
        @Returns  :
        -------
        """
        try:
            # id = self.docker_container.id
            # path_dir = os.path.dirname(path_file_Local)
            # # 从容器内部将文件复制到宿主机
            # cmd_get_doc = "docker cp {}:{} {}".format(id, path_file_inDocker, path_dir)
            # f = os.popen('echo %s|sudo -S %s' % (self.cfg["sys_info"]["psw"], cmd_get_doc))

            path_dir = os.path.dirname(path_file_Local)
            path_tar = os.path.join(path_dir, "result.tar")
            f = open(path_tar, 'wb')
            bits, stat = self.docker_container.get_archive(path_file_inDocker)
            for chunk in bits:
                f.write(chunk)
            f.close()
            with tarfile.open(path_tar, 'r') as f:
                f.extractall(path_dir)
            os.rename(os.path.join(path_dir, "result.json"), path_file_Local)
        except Exception as e:
            self.logger.error("复制文件错误")
            self.logger.error(e)
            return 1
        return 0
    
    # # 模型推理
    # def load_url_model(self, model_name):
    #     """
    #     @description  : 模型推理
    #     ---------
    #     @data_client  :
    #          data_path: 输入数据
    #        target_path: 保存路径
    #     -------
    #     @Returns      :
    #            success: 成功与否
    #            message: 详细信息
    #               data: 推理信息
    #     -------
    #     """

    #     result_json = {
    #         "input_data_type": "RGB",
    #         "output_data_type": "bounding_box",
    #         "results":{}}

    #     # assert self.path_task != "", "Error: task path is invalid"
    #     if self.path_task == "":
    #         self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
    #         print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")
        
    #     # 读取数据
    #     data_samples = os.path.join(self.path_task, self.cfg["data"]["data_image"], "samples")
    #     data_results = os.path.join(self.path_task, self.cfg["data"]["data_image"], "results")
    #     self._mkdir_path(data_results)
        
    #     data_list = os.listdir(data_samples)
    #     data_list = sorted(data_list)

    #     # 循环推理
    #     url = self.cfg['url']['detect_url'] + model_name
    #     print(url)
    #     for data_image in data_list:
    #         # 调用URL接口进行模型推理
    #         image_path = os.path.join(data_samples, data_image)
                
    #         image_base64 = self.get_image(image_path)
                
    #         data = {"dataBase64": image_base64}
    #         try:
    #             response = requests.post(url, data=json.dumps(data))
    #             json_data = response.json()

    #             code = json_data["code"]
    #             msg = json_data["msg"]
    #             data = json_data["data"]
    #             self.logger.info(msg)
                    
    #             if code == 0:
    #                 # [[61, 45, 200, 211, "class_2", 0.8787]]

    #                 # 保存到JSON文件
    #                 img_obj = []
    #                 for tar in data[0]:
    #                     bbox_info = {}
    #                     bbox_info["class_name"] = str(tar[4])
    #                     bbox_info["bbox"] = [int(tar[0]), int(tar[1]), int(tar[2]), int(tar[3])]
    #                     bbox_info["score"] = float(tar[5])
                    
    #                     img_obj.append(bbox_info)
    #                 print(img_obj)

    #                 result_json["results"][data_image] = img_obj
    #             else:
    #                 return {
    #                     "success": False,
    #                     "message": msg,
    #                     "data": data}
    #         except Exception as e:
    #             self.logger.error(e)
    #             return {
    #                 "success": False,
    #                 "message": str(e),
    #                 "data": {}}
        
    #     with open(target_path, "w") as file:
    #         file.write(json.dumps(result_json))
        
    #     return {
    #         "success": True,
    #         "message": msg,
    #         "data": target_path}
    
    def load_docker_image(self, path_docker):
        """
        @description  : 加载docker镜像包
        ---------
        @path_docker  : docker包存放路径
        -------
        @Returns      :
               success: 成功与否
               message: 详细信息
                  data: 镜像名称
        -------
        """

        # assert self.path_task != "", "Error: task path is invalid"
        if self.path_task == "":
            self.path_task = "./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1"
            print("Set path_task = ./db/a44d481e-29b5-48a2-9fa0-b3e0f24ef980/26d4d437-d82a-4629-94fb-5ea3dca88f40/task1")
        
        try:
            db_dir = os.path.join(self.path_task, self.cfg["data"]["data_image"])
            data_samples = os.path.join(self.path_task, self.cfg["data"]["data_image"], "samples")
            data_results = os.path.join(self.path_task, self.cfg["data"]["data_image"], "results")
            self._mkdir_path(data_results)
            
            # -----------------------------------------------------------
            # 模型推理
            result_path = os.path.join(db_dir, "label.json")
            if self.use_docker:
                
                # 加载tar并转成docker镜像
                if self.docker_tar:
                    # 白盒测试
                    print("----白盒测试......")
                    db_dir = os.path.join(self.path_task, self.cfg["data"]["data_image"])
                    path_docker_ = os.path.join(db_dir, path_docker)
                    # print(path_docker_)
                    if not os.path.exists(path_docker_):
                        self.logger.error("Can't find the image, some thing wrong with the path of docker")
                        return None
                    
                    self.docker_client = docker.from_env()  # 创建一个docker客户端
                    # 加载镜像
                    with open(path_docker_, 'rb') as f:
                        self.docker_image = self.docker_client.images.load(f)[0]
                        
                    self.model_name = self.docker_image.tags[0]
                else:
                    self.model_name = path_docker
                # print(self.model_name)
                
                path_mount_dataset = os.path.join(self.cfg["sys_info"]["project_root"], self.cfg["data"]["user_data"])  # 将数据集挂载到docker中
                # print("Path of mount: ", path_mount_dataset)
                vol = ["{}:/data".format(path_mount_dataset)]

                self.docker_client = docker.from_env()  # 创建一个docker客户端
                cmd_run_docker = '/bin/bash'
                self.docker_container = self.docker_client.containers.run(self.model_name,  # image_name 是我们docker镜像的name 
                                    detach=True,  # detach=True,是docker run -d 后台运行容器
                                    remove=True,  # 容器如果stop了，会自动删除容器
                                    tty=True,  # 分配一个tty  docker run -t
                                    volumes=vol,  # 与宿主机的共享目录， docker run -v /var/:/opt
                                    command=cmd_run_docker,
                                    device_requests=[docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])]
                                    )  # The command to run in the container
                self.logger.info('加载docker完成')
                
                res = self.run_docker_image(data_samples, result_path)
            else:
                self.model_name = path_docker
                if self.use_local_model:
                    # 白盒
                    # print("----白盒测试......")
                    res = self.local_infer(data_samples, result_path)
                else:
                    # 黑盒
                    print("----黑盒测试......")
                    res = self.model_infer(data_samples, result_path,  path_docker)
                    
            with open(result_path, 'r') as file:
                data = json.load(file)
                
            for key, value in data["results"].items():
                image = cv2.imread(os.path.join(data_samples, key))
                image_result = ret_result_image(value, image)
                cv2.imwrite(os.path.join(data_results, key), image_result)
            # ------------------------------------------------------------
                    
            if res["success"] == False:
                self.logger.error("--NO:失败加载模型")
                print("--NO:失败加载模型，模型推理错误，检查黑盒和白盒模型推理函数")
                return {
                    "success": False,
                    "message": res["msg"],
                    "data": res["data"]}
            
        except Exception as e:
            self.logger.error(e)
            print("--NO:失败加载模型")
            return {
                "success": False,
                "message": "Load model failed: " + str(e),
                "data": {
                        "code": 10 # 代表其他可能的错误
                }}
        
        self.logger.info("成功加载模型")
        print("--OK：成功加载模型")
        return {
            "success": True,
            "message": "Load model successfully!",
            "data": self.model_name}

        # sudoPassword = self.cfg["sys_info"]["psw"]
        # cmd_load_docker = "docker load -i %s"%(path_docker)
        # f = os.popen('echo %s|sudo -S %s' % (sudoPassword, cmd_load_docker))
        # cmd_ret = f.read()
        # image_name = cmd_ret[14:].strip()

#     # ok
#     def conditonal_test(self, data_client):
#         """
#         @description       :运行工况测试
#         ---------
#         @Author :
#         ---------
#         @client_condition  :web返回的请求参数
#         -------
#         @Returns  :
#         -------
#         """
#         # ret_class = []
#         # population_score = []
#         score_info = []

#         run_type = data_client["run_type"]
#         scene = self.cfg["scene"][2]
#         data_type = self.cfg["data_type"][0]
#         path_data = os.path.join(self.cfg["sys_info"]["project_root"], self.cfg["data"]["data_robust"], scene)
#         local_condition_config = self._loop_condition(data_type, scene)

#         path_basic_data = os.path.join(self.cfg["sys_info"]["project_root"], self.cfg["data"]["data_img"])
#         path_basic_samples = os.path.join(path_basic_data, "samples")

#         if run_type == 0:
#             user_code = data_client["code"]
#             # print(user_code)
            
#             for index_img, img_name in enumerate(os.listdir(path_basic_samples)):
#                 img = cv2.imread(os.path.join(path_basic_samples, img_name))
#                 noiseImg = img_noise(img)
#                 # Create a dictionary with the object to be passed to exec()
#                 exec_globals = {'noiseImg': noiseImg}

#                 exec(user_code, exec_globals)

#                 # Get the created objects from exec_globals
#                 noiseImg = exec_globals['noiseImg']

#                 if noiseImg.interference in local_condition_config.values():
#                     self.logger.info("工况数据已存在，可直接使用")
#                     break
#                 else:
#                     self.logger.info("所测试的工况数据不存在")
#                     # return ret_class, population_score, score_info
#                     return score_info
                
#             suitable_conditonfile = [k for k, v in local_condition_config.items() if v == noiseImg.interference][0]
#             path_condition = os.path.join(path_data, suitable_conditonfile)

#             if self.use_docker:
#                 self.run_docker_image(path_basic_data)
#                 self.get_files("/result/result.json")
#                 image_name = self.docker_image.tags[0]
#                 path_result = os.path.join(self.cfg["sys_info"]["project_root"], self.cfg["model"]["path_mount"], image_name.replace(":", "_"), "result.json")
#             else:
#                 path_data_test = os.path.join(path_condition, data_type, "samples")
#                 ret_ = self.load_local_model(self.path_model, path_data_test)
#                 path_result = os.path.join(self.path_model, "result/result.json")
        
#             path_label = os.path.join(path_condition, data_type, "label.json")
#             ret_json = self.calculator_basic_remote_sensing(path_result, path_label)
#             shutil.copyfile(path_result, os.path.join(path_condition, data_type, "result.json"))

#             # ret_class.append(self._score_class(ret_json["population_score"]))
#             # population_score.append(ret_json["population_score"])
#             score_info.append(ret_json)
#             # return ret_class, population_score, score_info
#             return score_info
#         else:
#             for index_condition_test, condition_num_test in enumerate(data_client["interference"]):
#                 if condition_num_test in local_condition_config.values():
#                     self.logger.info("工况数据已存在，可直接使用")
                    
#                     suitable_conditonfile = [k for k, v in local_condition_config.items() if v == condition_num_test][0]
#                     path_condition = os.path.join(path_data, suitable_conditonfile)
#                     print(path_condition)

#                     if self.use_docker:
#                         self.run_docker_image(path_basic_data)
#                         self.get_files("/result/result.json")
#                         image_name = self.docker_image.tags[0]
#                         path_result = os.path.join(self.cfg["sys_info"]["project_root"], self.cfg["model"]["path_mount"], image_name.replace(":", "_"), "result.json")
#                     else:
#                         path_data_test = os.path.join(path_condition, data_type, "samples")
#                         ret_ = self.load_local_model(self.path_model, path_data_test)
#                         path_result = os.path.join(self.path_model, "result/result.json")
        
#                     path_label = os.path.join(path_condition, data_type, "label.json")
#                     ret_json = self.calculator_basic_remote_sensing(path_result, path_label)
#                     shutil.copyfile(path_result, os.path.join(path_condition, data_type, "result.json"))

#                     # ret_class.append(self._score_class(ret_json["population_score"]))
#                     # population_score.append(ret_json["population_score"])
#                     score_info.append(ret_json)
#                 else:
#                     self.logger.info("所测试的工况数据不存在")
#             # return ret_class, population_score, score_info
#             ret_statistic_img(score_info[0])
#             return score_info

#     def ret_test(self, data_client):
#         """
#         @description       : 对创建完成的用户任务，执行噪声添加和结果检测，并对结果进行性能分析，将得到的中间图片进行保存
#         ---------
#         @Author            :
#         ---------
#         @data_client       : 噪声添加内容
#         -------
#         @Returns           : 原图、噪声图、结果图、性能图
#         -------
#         """
#         # 不运行createTask的情况下，方便调试
#         # self.path_task = "./db/baa079a9-d5b2-42d9-8d7c-15fdc4974cf0/63db1004-a617-4b27-9acf-b3eb05430e39/yolov5"
#         print(self.path_task)

#         # 仅用于测试
#         run_type = data_client["run_type"]
#         index_img = data_client["index_img"]

#         # 创建文件树
#         path_basic_data = os.path.join(self.path_task, self.cfg["data"]["data_img"])
#         path_noise_data = os.path.join(self.path_task, self.cfg["data"]["data_noise"])
#         path_result_data = os.path.join(self.path_task, self.cfg["data"]["data_result"])
#         self._mkdir_path(path_noise_data)
#         self._mkdir_path(path_result_data)

#         # 读取原始图片
#         img_list = []
#         dir_list = os.listdir(path_basic_data)
#         for dir in dir_list:
#             dir_path = os.path.join(path_basic_data, dir)
#             if os.path.isdir(dir_path):
#                 for img in os.listdir(dir_path):
#                     img_list.append(os.path.join(dir_path, img))
#         # print("num of img: ", len(img_list))

#         # 显示一张示例图片
#         if not 0 <= index_img < len(img_list):
#             print("index is not allowed, make it 0")
#             index_img = 0
        
#         result_json = {
#             # "task_type": "basic_effectiveness",
#             # "scenario": "remote_sensing",
#             # "input_data_type": "RGB",
#             # "output_data_type": "bounding_box",
#             "results":{}
#         }

#         # 循环处理图片
#         processed = False
#         for i, image_path in enumerate(img_list):
#             img_name = image_path.split("/")[-1]
#             img_org = cv2.imread(image_path)
#             _, img_org_encode = cv2.imencode('.jpg', img_org)
#             org_base64_byte  = img_org_encode.tobytes()
#             img_org_base64 = base64.b64encode(org_base64_byte).decode()

#             # 添加噪声
#             if run_type == 0:
#                 # 代码添加
#                 user_code = data_client["code"]
#                 noiseImg = img_noise(img_org)
                
#                 # 创建一个字典，其中包含要传递给 exec() 的对象
#                 exec_globals = {'noiseImg': noiseImg}
                
#                 exec(user_code, exec_globals)

#                 # Get the created objects from exec_globals
#                 noiseImg = exec_globals['noiseImg']
#                 img_noised = noiseImg.img
#                 noise_name = "".join(noiseImg.intensity)
#             else:
#                 # 数值添加
#                 interference = data_client["interference"]
#                 img_noised, noise_name = noiseSingleimg(img=img_org, interference=interference)
            
#             if i == 0:
#                 # 输出噪声文件夹名称
#                 print(noise_name)
#                 noise_path = os.path.join(path_noise_data, noise_name)
#                 result_path = os.path.join(path_result_data, noise_name)
            
#                 # 检查历史噪声工况，避免重复执行
#                 if os.path.exists(noise_path) and os.path.exists(result_path):
#                     print("存在历史噪声工况")
#                     processed = True
#                     img_noised = cv2.imread(os.path.join(noise_path, "sample_" + str(i).zfill(3) +".jpg"))
#                     _, img_noised_encode = cv2.imencode('.jpg', img_noised)
#                     noised_base64_byte  = img_noised_encode.tobytes()
#                     img_noised_base64 = base64.b64encode(noised_base64_byte).decode()

#                     img_result = cv2.imread(os.path.join(result_path, "sample_" + str(i).zfill(3) +".jpg"))
#                     _, img_result_encode = cv2.imencode('.jpg', img_result)
#                     result_base64_byte  = img_result_encode.tobytes()
#                     img_result_base64 = base64.b64encode(result_base64_byte).decode()
#                     break
#                 else:
#                     # 若不存在则执行以下逻辑
#                     self._mkdir_path(noise_path)
#                     self._mkdir_path(result_path)

#             cv2.imwrite(os.path.join(noise_path, img_name), img_noised)
#             _, img_noised_encode = cv2.imencode('.jpg', img_noised)
#             noised_base64_byte  = img_noised_encode.tobytes()
#             img_noised_base64 = base64.b64encode(noised_base64_byte).decode()

#             # 执行测试
#             ## 方法一：用URL进行目标检测
#             url = self.cfg['url']['detect_url']
#             # print("detect url: ", url)
#             data = {"dataBase64": img_noised_base64}
#             # print("data: ",data)
#             try:
#                 response = requests.post(url, json=data)
#                 # print(response.text)
#                 json_data = response.json()
#                 code = json_data["code"]
#                 msg = json_data["msg"]
#                 if code == 0:
#                     # [[61, 45, 200, 211, "class_2", 0.8787]]
#                     data_list = json_data["data"]

#                     # 保存到JSON文件
#                     img_obj = []
#                     for tar in data_list[0]:
#                         bbox_info = {}
#                         bbox_info["class_name"] = str(tar[4])
#                         bbox_info["bbox"] = [int(tar[0]), int(tar[1]), int(tar[2]), int(tar[3])]
#                         bbox_info["score"] = float(tar[5])
                    
#                     img_obj.append(bbox_info)
#                     print(img_obj)
#                     result_json["results"][img_name] = img_obj

#                     img_result = ret_result_img(data_list, img_noised)
#                     cv2.imwrite(os.path.join(result_path, img_name), img_result)
#                     _, img_result_encode = cv2.imencode('.jpg', img_result)
#                     result_base64_byte  = img_result_encode.tobytes()
#                     img_result_base64 = base64.b64encode(result_base64_byte).decode()
#                 else:
#                     print("测试错误")
#                     self.logger.error(msg)
#                     return "Result error!"
#             except Exception as e:
#                 print("error: " + response.text)
#                 self.logger.error(e)
#                 return "Result error!"
            
#             if i == index_img:
#                 ret = {
#                     "img": img_org_base64,
#                     "noised": img_noised_base64,
#                     "result": img_result_base64
#                 }
        
#         # 将检测结果保存到JSON文件中
#         path_result = os.path.join(result_path, "result.json")
#         if not processed:
#             with open(path_result, "w") as f_result:
#                 f_result.write(json.dumps(result_json))

#         # 进行结果性能评估
#         score_info = []
        
#         # 创建要写入的数据
#         data_to_write = {"labels": {"sample_000.jpg": [{"class_name": "ship", "bbox": [129, 214, 177, 300]}], "sample_001.jpg": [{"class_name": "ship", "bbox": [116, 539, 151, 629]}], "sample_002.jpg": [{"class_name": "ship", "bbox": [139, 725, 154, 817]}]}}

#         # 指定要保存的文件路径
#         path_label = os.path.join(path_basic_data, "label.json")

#         # 写入 JSON 文件
#         with open(path_label, 'w') as json_file:
#             json.dump(data_to_write, json_file, indent=4)
        
#         ret_json = self.calculator_basic_remote_sensing(path_result, path_label)
#         score_info.append(ret_json)
#         print(score_info)
#         img_eval_base64 = ret_statistic_img(score_info[0])

#         ret = {
#             "img": img_org_base64, 
#             "noised": img_noised_base64,
#             "result": img_result_base64,
#             "eval": img_eval_base64
#         }
#         return ret

#     # ok
#     def get_files(self, path_file_inDocker, path_save="tmp/image", docker_python=True):
#         """
#         @description         :将docker中的文件复制到宿主机中
#         ---------
#         @path_file_inDocker  :docker中的路径，必须是容器中的绝对路径
#         @docker_python       :使用docker for python 库复制文件
#         -------
#         @Returns             :
#         -------
#         """
#         if docker_python:
#             image_name = self.docker_image.tags[0]
#             save_dir = image_name.replace(":", "_")

#             file_name = path_file_inDocker.split("/")[-1]
#             path_tar = os.path.join(path_save, save_dir, file_name.replace(file_name.split(".")[-1], "tar"))
#             path_save = os.path.join(path_save, save_dir)
#             f = open(path_tar, 'wb')
#             try:
#                 bits, stat = self.docker_container.get_archive(path_file_inDocker)
            
#                 for chunk in bits:
#                     f.write(chunk)
#                 f.close()
#                 with tarfile.open(path_tar, 'r') as f:
#                     f.extractall(path_save)
#             except Exception as e:
#                 self.logger.error("复制文件错误")
#                 self.logger.error(e)
#                 return 1
#         else:
#             cmd_docker = 'ls /result'
#             code,stream = self.docker_container.exec_run(cmd_docker, stream=True)  # 返回一个元组 (exit_code, output)   stream就是我们的ls的返回值,但是需要decode一下
#             s = ''   
#             for x in stream:
#                 s += x.decode()
#             self.logger.info("ls "+s)
#             id = self.docker_container.id
#             # 从容器内部将文件复制到宿主机
#             cmd_get_doc = "docker cp {}:{} {}{}".format(id, path_file_inDocker,self.cfg["sys_info"]["project_root"], path_save)

#             f = os.popen('echo %s|sudo -S %s' % (self.cfg["sys_info"]["psw"], cmd_get_doc))
    
# #''''''暂时不用

#     def ret_demoimg(self, data_client):
#         """
#         @description      :根据用户python文件中的参数或前端选择参数，实时增加干扰，生成预览图片
#         ---------
#         @data_client  :
#         -------
#         @Returns          :预览图片
#         -------
#         """
#         run_type = data_client["run_type"]
#         index_img = data_client["index_img"]

#         path_basic_data = os.path.join(self.cfg["data"]["data_img"])
#         path_basic_samples = os.path.join(path_basic_data, "samples")

#         img_list = os.listdir(path_basic_samples)
#         if not 0 <= index_img < len(img_list):
#             print("index is not allowed, make it 0")
#             index_img = 0
        
#         path_img_select = os.path.join(path_basic_samples, img_list[index_img])
#         img_org = cv2.imread(path_img_select)

#         if run_type == 0:
#             user_code = data_client["code"]
#             noiseImg = img_noise(img_org)
            
#             # 创建一个字典，其中包含要传递给 exec() 的对象
#             exec_globals = {'noiseImg': noiseImg}
            
#             exec(user_code, exec_globals)

#             # Get the created objects from exec_globals
#             noiseImg = exec_globals['noiseImg']
#             img_noised = noiseImg.img
#         else:
#             interference = data_client["interference"]
#             img_noised = noiseSingleimg(img=img_org, interference=interference)

        
#         _, img_noised = cv2.imencode('.jpg', img_noised)
#         base64_byte  = img_noised.tobytes()
#         ret = base64.b64encode(base64_byte)
#         return ret

#     def watch_model_info(self, path_config):
#         """
#         @description  :查看模型简况
#         ---------
#         @path_config  : 模型配置文件的存放路径
#         -------
#         @Returns  :
#         -------
#         """
#         self.model_info = {"model_name":'', "default_cmd":'', "scene":0, "default_data_path":'', "data_type":0}

#         # if not self.use_docker:
#             # 加载被测算法的配置文件
#         self.logger.info("加载被测算法的配置文件")

#         if os.path.exists(path_config):
#             with open(path_config, 'r') as f:
#                 model_cfg = yaml.safe_load(f)
#             f.close()
#             try:
#                 self.model_info["model_name"] = model_cfg["MODEL"]["name"]
#                 self.model_info["default_cmd"] = model_cfg["MODEL"]["default_cmd"]
#                 self.model_info["scene"] = model_cfg["MODEL"]["scene"]
#                 self.model_info["description"] = model_cfg["MODEL"]["description"]
#                 self.model_info["default_data_path"] = os.path.join(self.cfg["sys_info"]["project_root"], "db", self.task_type, self.cfg["scene"][model_cfg["MODEL"]["scene"]])
#             except Exception as e:
#                 self.logger.error("被测算法键值错误")
#                 self.logger.error(e)
#                 return 1
#         else:
#             self.logger.error("被测算法的配置文件不存在，请检查配置文件的存放路径")
#             return 1
#         """
#         else:
#             # 这里主要因为docker还没有调通，理论上应该将images中的config复制出来再读取
#             if "guidance" in path_config:
#                 self.model_info["default_cmd"] = "docker run -it -v /db/basic_effectiveness/guidance/sample:/data"
#                 self.model_info["model_name"] = "KCFObjectTracking"
#                 self.model_info["scene"] = 0
#                 self.model_info["default_data_path"] = "/db/basic_effectiveness/guidance/sample"
#             elif "navigation" in path_config:
#                 self.model_info["default_cmd"] = "docker run -it -v /db/basic_effectiveness/navigation/sample:/data"
#                 self.model_info["model_name"] = "配准"
#                 self.model_info["scene"] = 1
#                 self.model_info["default_data_path"] = "/db/basic_effectiveness/navigation/sample"
#             elif "remote_sensing" in path_config:
#                 self.model_info["default_cmd"] = "docker run -it -v /db/basic_effectiveness/remote_sensing/sample:/data"
#                 self.model_info["model_name"] = "YOLO"
#                 self.model_info["scene"] = 2
#                 self.model_info["default_data_path"] = "/db/basic_effectiveness/remote_sensing/sample"
#             else:
#                 self.model_info["default_cmd"] = "docker run -it -v /db/basic_effectiveness/voice/sample:/data"
#                 self.model_info["model_name"] = "Speech_aa"
#                 self.model_info["scene"] = 3
#                 self.model_info["default_data_path"] = "/db/basic_effectiveness/voice/sample"
#         """

#         return 0

#     def _score_class(self, score):
#         score = 100 * score
#         if score >= 80:
#             ret = "5"
#         elif 60 <= score < 80:  
#             ret = "4"
#         elif 40 <=score <60:
#             ret = "3"
#         elif 20 <=score <40:
#             ret = "2"
#         else:
#             ret = "1"
#         return ret
    
#     def ret_performance(self, data_client):
#         """
#         @description    :返回性能指标
#         ---------
#         @param          :
#         -------
#         @Returns        :
#         -------
#         """
#         url = self.cfg['url']['detect_url']
#         index_img = data_client["index_img"]

#         path_basic_data = os.path.join(self.cfg["data"]["data_img"])
#         path_basic_samples = os.path.join(path_basic_data, "samples")

#         img_list = os.listdir(path_basic_samples)
#         print(img_list)
#         if not 0 <= index_img < len(img_list):
#             print("index is not allowed, make it 0")
#             index_img = 0

#         path_img_select = os.path.join(path_basic_samples, img_list[index_img])
#         print(path_img_select)
#         img_org = cv2.imread(path_img_select)

#         output_image_path = os.path.join("./tmp", img_list[index_img])

#         # 计算原始图片的平均置信度
#         _, img_encode = cv2.imencode('.jpg', img_org)
#         base64_byte  = img_encode.tobytes()
#         img_base64 = base64.b64encode(base64_byte).decode()
#         data = {"dataBase64": img_base64}
#         try:
#             response = requests.post(url, json=data)
#             json_data = response.json()
#             code = json_data["code"]
#             msg = json_data["msg"]
#             if code == 0:
#                 data_list = json_data["data"]
#                 print(data_list)
#                 score_org = ret_result_score(data_list)
#                 print(score_org)
#             else:
#                 self.logger.error(msg)
#         except Exception as e:
#             self.logger.error(e)

#         score = []
#         for i in range(4):
#             # 计算不同因素噪声指标
#             denominator = 0.0 # 分母
#             numerator = 0.0 # 分子
#             noise_list = self.cfg["robustness"]["interferenceType"][i]
#             print(noise_list)
#             for n in noise_list:
#                 set_value = self.cfg["robustness"]["defaultCondition"][i][n]
#                 interference = {n: set_value}
#                 print(interference)

#                 denominator += set_value["weight"]

#                 img_noised = noiseSingleimg(img=img_org, interference=interference, input_image_path=path_img_select, output_image_path=output_image_path)
#                 # cv2.imwrite(os.path.join("./tmp/noise", n+".jpg"), img_noised)

#                 _, img_noised_encode = cv2.imencode('.jpg', img_noised)
#                 noised_base64_byte  = img_noised_encode.tobytes()
#                 noised_img_base64 = base64.b64encode(noised_base64_byte).decode()

#                 noised_data = {"dataBase64": noised_img_base64}
#                 try:
#                     response = requests.post(url, json=noised_data)
#                     json_data = response.json()
#                     code = json_data["code"]
#                     msg = json_data["msg"]
#                     if code == 0:
#                         data_list = json_data["data"]
#                         print(data_list)
#                         score_noised = ret_result_score(data_list)
#                         print(score_noised)
#                         numerator += (1 - (abs(score_org - score_noised))) * set_value["weight"]

#                         img_result = ret_result_img(data_list, img_noised)
#                         print(n)
#                         # cv2.imwrite(os.path.join("./tmp/test", n+".jpg"), img_result)
#                     else:
#                         self.logger.error(msg)
#                 except Exception as e:
#                     self.logger.error(e)
                
#             # print(numerator)
#             # print(denominator)
#             W = numerator / denominator
#             print(W)
#             score.append(W)
#         return score