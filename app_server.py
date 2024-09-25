# !/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@Description:       : 网页服务器,定义路由,调用app_fun实现具体函数
@Date               : 2023/11/10 8:57
@Author             : Zhang Rujia
@version            : 2.0
'''

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from src.app.app_fun import App_fun
import os, shutil, json

app_fun = App_fun()

app = Flask(__name__)
CORS(app, resources=r'/*')	# 注册CORS, "/*" 允许访问所有api解决跨域问题

# 通信测试
@app.route('/sendtry', methods=["POST"])
def sendtry():
   data_client = request.get_json()
   print(data_client)
   return 'hahaha'

# 测试直接传数据
@app.route('/sendcodetry', methods=["POST"])
def sendcodetry():
   data_client = request.get_data()
   print(data_client)
   return 'getcode'

# 测试form
@app.route('/sendcodeformtry', methods=["POST"])
def sendcodeformtry():
   data_client = request.form.get('ax')
   print(data_client)
   return 'getcode'

# 0
@app.route('/', methods=["GET"])
def main_page():
   return 'Robustness'

# 1 获取用户权限信息
@app.route("/getPermission", methods=["POST"])
def getPermission():
   """
   @description   : 获取用户权限信息
   ---------
   @param         :
                id: session ID
            projid: 项目ID
   -------
   @Returns       :
           success: 成功与否
           message: 详细信息
             token: token值
   -------
   """
   data_client = request.get_json()
   print(data_client)
   ret = app_fun.request_permission(data_client)
   return jsonify(ret)

# 未登录时获取令牌
@app.route("/get_notlog_token", methods=["POST"])
def get_notlog_token():
   """
   @description   : 智能测评系统页面未登录，使用accessKey，secretKey获取令牌。
   ---------
   @param         :
            accessKey: 公钥	
            secretKey: 私钥
   -------
   @Returns       :
                  code: 状态码
               success: 成功与否
               message: 详细信息
                 data: token值
   -------
   """
   ret = app_fun.Request_notlog_token()
   return jsonify(ret)

# 结果回传
@app.route("/get_SendResult", methods=["POST"])
def get_SendResult():
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
   ret = app_fun.Request_SendResult()
   return jsonify(ret)


# 2 创建鲁棒性测评子任务
@app.route("/robustness/createTask", methods=["GET"])
def ret_createTask():
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
   args = request.args
   print("\n--createTask:创建子任务 taskName:{}, projectId:{}, taskId:{}".format(args["taskName"], args["projectId"], args["taskId"]))
   print("----" + str(args.to_dict()))
   ret = app_fun.createTask(args)
   return jsonify(ret)

# 3 获取子任务信息
@app.route("/robustness/taskInfo", methods=["GET"])
def ret_taskInfo():
   """
   @description  : 返回projectId已创建任务信息
   ---------
   @param        :
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
   args = request.args
   print("\n--taskInfo:返回projectId:{},taskId:{}已创建任务信息".format(args["projectId"], args["taskId"]))
   print("----" + str(args.to_dict()))
   ret = app_fun.get_taskInfo(args)
   return jsonify(ret)

# 4 选择鲁棒性测评子任务
@app.route("/robustness/setTask", methods=["GET"])
def ret_setTask():
   """
   @description   : 选择鲁棒性测评子任务
   ---------
   @param         :
      projectId   : 项目ID
      taskId      : 任务ID
      taskName    : 任务名称
   -------
   @Returns       :
           success: 成功与否
           message: 详细信息
              data: 是否存在历史结果或none
   -------
   """
   args = request.args
   print("\n--setTask:选择taskName:{}, projectId:{}, taskId:{}".format(args["taskName"], args["projectId"], args["taskId"]))
   print("----" + str(args.to_dict()))
   taskId = args["taskId"]
   # algorithmNo = args["algorithmNo"]
   path_task = os.path.join("./", app_fun.cfg["data"]["user_data"], args["projectId"], args["taskId"], args["taskName"])
   ret = app_fun.setTask(path_task, taskId)
   # ret = app_fun.setTask(path_task, taskId)
   return jsonify(ret)
   '''
   try:
      if os.path.exists(path_task):
         app_fun.path_task = path_task
         path_json = os.path.join(path_task, 'info.json')
         # 读取 JSON 文件内容
         with open(path_json, 'r') as f:
            info = json.load(f)
         key = 'result'
         if key in info:
            history = True
         else:
            history = False
            
         return jsonify({
               "success": True,
               "message": "set task '" + path_task + "' success",
               "data": history})
      else:
         return jsonify({
               "success": False,
               "message": "task '" + path_task + "' doesn't exist",
               "data": None})
   except Exception as e:
      return jsonify({
         "success": False,
         "message": str(e),
         "data": None})
   '''

# 5 删除鲁棒性测评子任务
@app.route("/robustness/deleteTask", methods=["GET"])
def ret_deleteTask():
   """
   @description   : 删除鲁棒性测评子任务
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
   args = request.args
   print("\n--deleteTask:删除子任务 taskName:{}, projectId:{}, taskId:{}".format(args["taskName"], args["projectId"], args["taskId"]))
   print("----" + str(args.to_dict()))
   path_root = os.path.join("./", app_fun.cfg["data"]["user_data"], args["projectId"])
   path_dir = os.path.join(path_root, args["taskId"])
   path_task = os.path.join(path_dir, args["taskName"])
   try:
      if not os.path.exists(path_task):
         print("--NO：删除子任务失败，错误信息：不存在对应的projectId,taskId或taskName，请检查")
         app_fun.logger.error("ERROR:There is no corresponding projectId, taskId or taskName.")
         return {
            "success": False,
            "message": "ERROR:There is no corresponding projectId, taskId or taskName.",
            "data": {
               "code": 1 # code为0代表后端不存在相应的projectId,taskId和taskName路径，需要检查
            }}
      shutil.rmtree(path_task)
      tasks = os.listdir(path_dir)
      if len(tasks) == 0:
         shutil.rmtree(path_root)
      app_fun.logger.info("成功删除子任务"  + args["taskName"])
      print("--OK：成功删除子任务"  + args["taskName"])
      return jsonify({
            "success": True,
            "message": "delete taskName:" + args["taskName"] + ", taskId:" + args["taskId"] + ", projectId:" + args["projectId"] + " success"})
   except Exception as e:
      app_fun.logger.error(e)
      print("--NO：删除子任务失败，错误信息：" + str(e))
      return jsonify({
            "success": False,
            "message": str(e),
            "data": {
               "code": 10 # 其他可能的错误
            }})

# 6 获取数据列表
@app.route("/robustness/getDatalist", methods=["GET"])
def get_Datalist():
   """
   @description  : 发送查询条件到主平台，主平台返回满足条件的数据列表
   ---------
   @param        :
    MS_SESSION_ID: session ID
        projectId: 项目ID
           prefix: 查询条件
             page: 分页索引
         pageSize: 分页大小
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 数据列表信息
   -------
   """
   args = request.args
   print("\n--getDatalist:获取数据列表")
   print("----" + str(args.to_dict()))
   ret = app_fun.request_datalist(args)
   return jsonify(ret)

# 7 加载数据
@app.route("/robustness/getData", methods=["POST"])
def get_Data():
   """
   @description  : 选择数据列表内的数据，加载对应的数据到本地
   ---------
   @param        :
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
   data_client = request.get_json()
   print("\n--getData:获取数据")
   print("----" + str(data_client))
   ret = app_fun.request_data(data_client)
   return jsonify(ret)

# 8 调用URL接口进行模型推理
@app.route("/robustness/modelInfer", methods=["POST"])
def model_Infer():
   """
   @description  : 调用URL接口进行模型推理
   ---------
   @param        :
        data_path: 输入数据列表
      target_path: 保存路径
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 推理信息
   -------
   """
   data_client = request.get_json()
   print(data_client)
   ret = app_fun.model_infer(data_client["data_path"], data_client["target_path"], data_client["model_name"])
   return jsonify(ret)

# 9 可选干扰类型
@app.route("/robustness/retType", methods=["GET"])
def ret_Type():
   """
   @description  : 可选干扰类型
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 推理信息
   -------
   """
   try:
      ret = app_fun.cfg["robustness"]["interferenceType"]
      return jsonify({
            "success": True,
            "message": "get 17 types noise success",
            "data": ret})
   except Exception as e:
      return jsonify({
            "success": False,
            "message": str(e),
            "data": {}})

# 10 生成扰动样本
@app.route("/robustness/generateData", methods=["POST"])
def generate_Data():
   """
   @description  : 生成扰动样本
   ---------
   @data_client  :
         run_type: 生成方式
             code: 代码
     interference: 噪声强度
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 生成扰动样本信息
   -------
   """
   data_client = request.get_json()
   print("\n--generateData:添加噪声")
   # print("----run_type:" + str(data_client["run_type"]))
   ret = app_fun.generate_data(data_client)
   return jsonify(ret)

# 11 噪声样本测试结果
@app.route("/robustness/retResult", methods=["GET"])
def ret_Result():
   """
   @description  : 噪声样本测试结果
   ---------
   @param        :
       noise_name: 噪声强度名
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 生成扰动样本信息
   -------
   """
   args = request.args
   print("\n--retResult:计算噪声样本测试结果")
   print("----" + str(args.to_dict()))
   ret = app_fun.ret_result(args)
   return jsonify(ret)

#二级指标  噪声样本测试结果
@app.route("/robustness/ret_sec_score_result", methods=["POST"])
def ret_sec_score_result():
   """
   @description  : 二级指标 噪声样本列表测试结果
   ---------
   @param        :
       noise_name_list: 噪声强度名列表
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 生成扰动样本信息
   -------
   """
   data_client = request.get_json()
   print("\n--ret_sec_score_result:生成用于计算二级指标的中间文件")
   print("----" + str(data_client["noise"]["allnoise"]))
   ret = app_fun.ret_sec_score_result(data_client)
   return jsonify(ret)

# 12 返回原始、噪声和测试结果图片
@app.route("/robustness/retImage", methods=["GET"])
def ret_Image():
   """
   @description  : 返回原始、噪声和测试结果图片
   ---------
   @param        :
            index: 测试图片序号
       noise_name: 噪声强度名
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 图片信息
   -------
   """
   args = request.args
   print("\n--retImage:返回示例结果图片")
   print("----" + str(args.to_dict()))
   ret = app_fun.ret_result_image(int(args["index"]), args["noise_name"])
   return jsonify(ret)

# 返回噪声推理结果图片
@app.route("/robustness/ret_noise_img", methods=["GET"])
def ret_noise_img():
   """
   @description  : 返回五张噪声推理结果图
   ---------
   @param        :
       noise_name: 噪声强度名
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
         img_list: 五张噪声推理结果图
   -------
   """
   args = request.args
   print("\n--ret_noise_img:返回噪声推理结果图")
   print("----" + str(args.to_dict()))
   ret = app_fun.ret_noise_img(args["noise_name"])
   return jsonify(ret)



# 13 返回三级指标分数
@app.route("/robustness/ret_third_score", methods=["GET"])
def ret_Performace():
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
   args = request.args
   print("\n--ret_third_score:三级指标分数")
   print("----" + str(args.to_dict()))
   ret = app_fun.ret_third_score(args["noise_name"])
   return jsonify(ret)

# 返回二级指标分数
@app.route("/robustness/ret_sec_score", methods=["POST"])
def ret_sec_score():
   """
   @description  : 返回二级指标分数
   ---------
   @data_client  :
       noise_name_list: 二维加噪列表
                  {
                     "noise": {
                        "fastsnow": [
                              "00000000000100000",
                              "00000000000200000",
                              "00000000000300000",
                              "00000000000300000"
                        ],
                        "motionblur": [
                              "00000000010000000",
                              "00000000020000000",
                              "00000000030000000",
                              "00000000020000000"
                        ],
                        "allnoise": [
                              "00000000010100000"
                        ]
                     }
                  }
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 生成扰动样本信息
   -------
   """
   data_client = request.get_json()
   print("\n--ret_sec_score:计算二级指标")
   # print("----" + str(data_client))
   ret = app_fun.ret_sec_score(data_client)
   return jsonify(ret)
   

@app.route("/robustness/ret_SSIM_score", methods=["GET"])
def ret_SSIM_score():
   ret = app_fun.ret_SSIM_score()
   return jsonify(ret)

# 返回一级指标分数
@app.route("/robustness/ret_fst_score", methods=["POST"])
def ret_fst_score():
   """
   @description  : 返回一级指标分数
   ---------
   @data_client  :
      ssim_dic: SSIM分数
      score_sec_dic: 二级指标分数
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
        score_fst: 一级指标分数
   -------
   """
   data_client = request.get_json()
   print(data_client)
   ret = app_fun.ret_fst_score(data_client)
   return jsonify(ret)

# 14 获取模型列表
@app.route("/robustness/getImagelist", methods=["GET"])
def get_Imagelist():
   """
   @description  : 发送查询条件到主平台，主平台返回满足条件的模型列表
   ---------
   @param        :
    MS_SESSION_ID: session ID
        projectId: 项目ID
           prefix: 查询条件
             page: 分页索引
         pageSize: 分页大小
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 模型列表信息
   -------
   """
   args = request.args
   print("\n--getImagelist:获取模型列表")
   print("----" + str(args.to_dict()))
   ret = app_fun.request_imagelist(args)
   return jsonify(ret)

# 7 加载数据
@app.route("/robustness/getImage", methods=["POST"])
def get_Image():
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
   data_client = request.get_json()
   print("\n--getImage:获取白盒模型")
   print("----" + str(data_client))
   ret = app_fun.request_image(data_client)
   return jsonify(ret)

# 15 加载docker镜像包
@app.route("/robustness/loadImage", methods=["GET"])
def load_Image():
   """
   @description  : 加载docker镜像包运行或直接运行镜像
   ---------
   @param        :
    path_docker  : docker包存放路径
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 镜像名称
   -------
   """
   args = request.args
   print("\n--loadImage:加载模型")
   print("----" + str(args.to_dict()))
   path_task = app_fun.path_task
   try:
      # with open(os.path.join(path_task, "info.json"), 'r') as file:
      #    data = json.load(file)
      # test_type = data["test_type"]
      # if test_type == "white":
      #    app_fun.use_docker = True
      #    app_fun.docker_tar = True
      #    data_client = {
      #       "MS_SESSION_ID": args["MS_SESSION_ID"],
      #       "projectId": args["projectId"],
      #       "objectNameArr": [args["path_docker"]]
      #    }
      #    app_fun.request_image(data_client)
      # elif test_type == "black":
      #    app_fun.use_docker = False
      #    app_fun.use_local_model = False
      # else:
      #    return jsonify({
      #       "success": False,
      #       "message": "The test type of task can ben processed."})
      ret = app_fun.load_docker_image(args["path_docker"])
   except Exception as e:
      return jsonify({
         "success": False,
         "message": str(e)})
   return jsonify(ret)
   # return "hi"

# 16 报告回传
@app.route("/robustness/getReport", methods=["GET"])
def get_Report():
   """
   @description  : 报告回传
   ---------
   @param        :
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
   args = request.args
   print(args)
   ret = app_fun.get_report(args)
   print(ret)
   return jsonify(ret)

# 17 获取历史子任务结果列表
@app.route("/robustness/getHistorylist", methods=["GET"])
def get_Historylist():
   """
   @description  : 获取历史子任务结果列表
   ---------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 数据列表信息
   -------
   """
   ret = app_fun.request_historylist()
   return jsonify(ret)

# 18 返回噪声强度表
@app.route("/robustness/getNoise", methods=["GET"])
def get_Noise():
   """
   @description  : 返回噪声强度表
   ---------
   @param        :
       noise_name: 噪声强度名
   ---------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 数据列表信息
   -------
   """
   args = request.args
   print(args)
   ret = app_fun.get_noise(args)
   return jsonify(ret)

# 19 获取指标图
@app.route("/robustness/getPerform", methods=["GET"])
def get_Perform():
   """
   @description  : 获取指标图
   ---------
   @param        :
        imagepath: 图片地址
   ---------
   @Returns      :
   -------
   """
   args = request.args
   imagepath = args["imagepath"]
   try:
      return send_file(imagepath)
   except Exception as e:
      return str(e)

# 20 本地模型推理
@app.route("/robustness/localInfer", methods=["POST"])
def local_Infer():
   """
   @description  : 本地模型推理
   ---------
   @param        :
        data_path: 输入数据列表
      target_path: 保存路径
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 推理信息
   """
   data_client = request.get_json()
   print(data_client)
   ret = app_fun.local_infer(data_client["data_path"], data_client["target_path"])
   return jsonify(ret)

# 21 在容器中运行被测算法
@app.route("/robustness/runImage", methods=["GET"])
def run_Image():
   """
   @description  : 完成加载docker后，在容器中运行被测算法
   ---------
   @param        :
    path_data    : 传送给被测算法的，数据集路径
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 
   -------
   """
   args = request.args
   print(args)
   ret = app_fun.run_docker_image(args["path_data"])
   print(ret)
   return jsonify(ret)

# 预设工况生成扰动样本
@app.route("/robustness/preConditions", methods=["GET"])
def pre_Conditions():
   """
   @description  : 预设工况
   ---------
   @data_client  :
      conditionId: 调用工况序号
   -------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 生成扰动样本信息
   -------
   """
   args = request.args
   print("\n--preConditions:预设工况添加噪声")
   print("----" + str(args.to_dict()))
   ret = app_fun.pre_conditions(args["conditionId"])
   return jsonify(ret)

# 返回预设工况名称
@app.route("/robustness/getpreConName", methods=["GET"])
def get_preConName():
   """
   @description  : 返回预设工况名称
   ---------
   @param        :
      conditionId: 预设工况序号
   ---------
   @Returns      :
          success: 成功与否
          message: 详细信息
             data: 预设工况名称信息
   -------
   """
   args = request.args
   print(args)
   ret = app_fun.get_preConName(args["conditionId"])
   return jsonify(ret)

def create_app():
   app.run(host='0.0.0.0', port=7070, debug=True)
