
# encoding = utf-8

import os
import sys
import time
import datetime
import json

def validate_input(helper, definition):
    api_env = definition.parameters.get('api_env', None)
    instanceid = definition.parameters.get('instance_id', None)
    apikey = definition.parameters.get('apikey', None)
    api_limit = definition.parameters.get('api_limit', None)
    api_timeout = definition.parameters.get('api_timeout', None)
    pass

def collect_events(helper, ew):
    # Retrieve runtime variables
    opt_environment = helper.get_arg('api_env')
    opt_instanceid = helper.get_arg('instance_id') or helper.get_global_setting('instance_id')
    opt_apikey = helper.get_arg('apikey') or helper.get_global_setting('apikey')
    opt_limit = helper.get_arg('api_limit')
    opt_timeout = float(helper.get_arg('api_timeout'))

    # Create checkpoint key
    opt_checkpoint = "alerts_" + opt_environment + "_" + opt_instanceid
    #Create last status entry for storage as checkpoint
    current_status = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    #Check for last query execution data in kvstore & generate if not present
    try:
        last_status = helper.get_check_point(opt_checkpoint) or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(0))
        helper.log_debug("[" + opt_instanceid + "] Helix Alerts - Last successful checkpoint time: " + str(last_status))
    except Exception as e:
        helper.log_error("[" + opt_instanceid + "] Helix Alerts - Unable to retrieve last execution checkpoint!")
        raise e

    # use simple rest call to load the events
    header = {}
    data = {}
    parameter = {}
    parameter['limit'] = opt_limit
    parameter['sort'] = "-createDate"
    parameter['withCount'] = "1"
    parameter['includes'] = "revisions._updatedBy"
    parameter['query'] = str('{"updateDate":{"$gte":"' + last_status + '"}}')
    url = "https://" + opt_environment + ".fireeye.com/helix/id/" + opt_instanceid + "/api/v1/alerts"
    method = 'GET'
    header['x-fireeye-api-key'] = opt_apikey

    try:
        # Leverage helper function to send http request
        response = helper.send_http_request(url, method, parameters=parameter, payload=None, headers=header, cookies=None, verify=True, cert=None, timeout=opt_timeout, use_proxy=True)

        # Return API response code
        r_status = response.status_code
        # Return API request status_code
        if r_status is not 200:
            helper.log_error("[" + opt_instanceid + "] Alerts API unsuccessful status_code=" + str(r_status))
            response.raise_for_status()
        # Return API request as JSON
        obj = response.json()

        if obj is None:
            helper.log_info("[" + opt_instanceid + "] No new alerts retrieved from Helix.")

        # Iterate over alerts in array & index
        i=0
        for alert in obj.get("alerts"):
            singleAlert = (obj.get("alerts")[i])
            singleAlert['helix_instance'] = opt_instanceid
            singleAlert['helix_environment'] = opt_environment
            
            # Rename underscore fields so Splunk will index values
            singleAlert['updatedBy'] = singleAlert['_updatedBy']
            singleAlert['createdBy'] = singleAlert['_createdBy']
            singleAlert['assignedTo'] = singleAlert['_assignedTo']
            # Remove underscore fieldnames and values
            del singleAlert['_updatedBy']
            del singleAlert['_createdBy']
            del singleAlert['_assignedTo']

            event = helper.new_event(source=helper.get_input_type(), index=helper.get_output_index(), sourcetype=helper.get_sourcetype(), data=json.dumps(singleAlert))
            
            try:
                ew.write_event(event)
                helper.log_debug("[" + opt_instanceid + "] Added alert:" + str(singleAlert['id']))
            except Exception as error:
                helper.log_error("[" + opt_instanceid + "] Unable to add alert:" + str(singleAlert['id']))
            i = i + 1

        #Update last completed execution time
        helper.save_check_point(opt_checkpoint, current_status)
        helper.log_info("[" + opt_instanceid + "] Alerts collection complete. Records added: " + str(i))
        helper.log_debug("[" + opt_instanceid + "] Helix Alerts - Storing checkpoint time: " + current_status)

    except Exception as error:
        helper.log_error("[" + opt_instanceid + "] Helix Alerts - An unknown error occurred!")
        raise error