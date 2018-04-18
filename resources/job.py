# -*- coding:utf-8 -*-
from flask_restful import Resource, reqparse
from flask import g
from common.log import Logger
from common.audit_log import audit_log
from common.utility import salt_api_for_product
from common.sso import access_required
from common.const import role_dict
from common.db import DB

logger = Logger()

parser = reqparse.RequestParser()
parser.add_argument("product_id", type=str, required=True, trim=True)
parser.add_argument("action", type=str, trim=True)
parser.add_argument("jid", type=str, trim=True)
parser.add_argument("minion_id", type=str, trim=True, action="append")


class Job(Resource):
    @access_required(role_dict["common_user"])
    def get(self, job_id):
        args = parser.parse_args()
        salt_api = salt_api_for_product(args["product_id"])
        if isinstance(salt_api, dict):
            return salt_api, 500
        else:
            result = salt_api.jobs_info(job_id)
            return result, 200


class JobList(Resource):
    @access_required(role_dict["common_user"])
    def get(self):
        args = parser.parse_args()
        job_list = []
        # salt_api = salt_api_for_product(args["product_id"])
        # if isinstance(salt_api, dict):
        #     return salt_api, 500
        # else:
        #     result = salt_api.jobs_list()
        #     if isinstance(result, dict):
        #         for jid, info in result.items():
        #             # 不能直接把info放到append中
        #             info.update({"Jid": jid})
        #             job_list.append(info)
        db = DB()
        status, result = db.select("event", "where data -> '$.data.product_id'='%s' "
                                            "and data -> '$.data.jid'!='""' "
                                            "order by data -> '$.data._stamp' desc" % args["product_id"])
        db.close_mysql()
        if status is True:
            if result:
                for i in result:
                    try:
                        job_list.append(eval(i[0])['data'])
                    except Exception as e:
                        return {"status": False, "message": str(e)}, 500
        else:
            return {"status": False, "message": result}, 500
        return {"data": job_list, "status": True, "message": ""}, 200


class JobManager(Resource):
    @access_required(role_dict["common_user"])
    def get(self):
        args = parser.parse_args()
        salt_api = salt_api_for_product(args["product_id"])
        job_active_list = []
        if isinstance(salt_api, dict):
            return salt_api, 500
        else:
            result = salt_api.runner("jobs.active")
            if result:
                if result.get("status") is False:
                    return result, 500
                for jid, info in result.items():
                            # 不能直接把info放到append中
                            info.update({"Jid": jid})
                            job_active_list.append(info)
            return {"data": job_active_list, "status": True, "message": ""}, 200

    @access_required(role_dict["common_user"])
    def post(self):
        args = parser.parse_args()
        salt_api = salt_api_for_product(args["product_id"])
        user = g.user_info["username"]
        db = DB()
        status, result = db.select_by_id("product", args["product_id"])
        db.close_mysql()
        if status is True:
            if result:
                product = eval(result[0][0])
            else:
                return {"status": False, "message": "%s does not exist" % args["product_id"]}
        else:
            return {"status": False, "message": result}
        if isinstance(salt_api, dict):
            return salt_api, 500
        else:
            if args["action"] == "kill" and args["jid"] and args["minion_id"]:
                for minion in args["minion_id"]:
                    kill = "salt %s saltutil.kill_job %s" % (minion, args["jid"])
                    try:
                        result = salt_api.shell_remote_execution(product.get("salt_master_id"), kill)
                        audit_log(user, args["jid"], args["product_id"], "job id", "kill")
                        logger.info("kill %s %s return: %s" % (minion, args["jid"], result))
                    except Exception as e:
                        logger.info("kill %s %s error: %s" % (minion, args["jid"], e))
                return {"status": True, "message": ""}, 200
            else:
                return {"status": False, "message": "The specified jid or action or minion_id "
                                                    "parameter does not exist"}, 400
