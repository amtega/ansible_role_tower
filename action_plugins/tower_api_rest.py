#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from ansible.utils.display import Display
from urllib.parse import quote


class ActionModule(ActionBase):
    _display = Display()

    def _get_task_var(self, name, default=None):
        """Get templated task variable"""

        if name in self._task_vars:
            ret = self._templar.template(self._task_vars.get(name))
        else:
            ret = default

        return ret

    def _get_error(self, result):
        """Raise API REST error"""

        output = dict(
                    failed=True,
                    msg="Operation in {0} failed: {1}".format(
                        result["url"],
                        result["json"].get("msg",
                                           result["json"].get("detail",
                                                              result["msg"])))
        )

        return output

    def _call(self):
        """Call tower API REST"""

        try:
            # Setup variables with for call parameters

            tower_host = self._get_task_var("tower_host")
            token = self._task_vars["ansible_facts"]["tower_token"]
            path = self._task.args.get("path", None)
            method = self._task.args.get("method", "GET")
            fields = self._task.args.get("fields", {})
            search = self._task.args.get("search", "")
            absolute = self._task.args.get("absolute", False)
            validate_certs = self._get_task_var("validate_certs", True)

            # If path is not absoulte append base API REST path

            if not absolute:
                path = "/api/v2{path}".format(path=path)

            # Call the API rest and iterate all the pages returned

            add_args = len(search) > 0
            json = []
            next = "{path}".format(path=path)
            while next:
                url = "{host}{next}".format(host=tower_host, next=next)

                # Append extra args to url

                if add_args:
                    url = url + "?search={search}".format(search=quote(search))
                    add_args = False

                # Compose URI module args

                uri_args = dict(
                    url=url,
                    method=method,
                    headers={
                      "Authorization": "Bearer {token}".format(token=token),
                      "Content-Type": "application/json"
                    },
                    validate_certs=validate_certs,
                    follow_redirects="all",
                    return_content=True,
                    status_code=[200, 201, 202, 203, 204],
                )

                # If this is a POST call setup the body of the call

                if method in ["POST", "PATCH"]:
                    uri_args["body_format"] = "json"
                    uri_args["body"] = fields

                # Call URI module

                result = self._execute_module(module_name='uri',
                                              module_args=uri_args,
                                              task_vars=self._task_vars,
                                              tmp=self._tmp)

                self._display.vvv(
                              "{action} result: {result}"
                              .format(action=self._task.action, result=result))

                # Handle failed return status

                if result.get("failed", False):
                    return self._get_error(result)

                # Combine results from multiple pages

                result_json = result.get("json", dict())
                if "results" in result_json:
                    json += result_json["results"]
                else:
                    json = result_json

                # Retrieve next page url

                if not isinstance(result_json, list):
                    next = result_json.get("next", False)
                else:
                    next = False

            return dict(json=json,
                        status=result["status"],
                        msg=result["msg"])
        except Exception:
            return self._get_error(result)

    def run(self, tmp=None, task_vars=None):
        """Run the action module"""

        super(ActionModule, self).run(tmp, task_vars)
        self._tmp = tmp
        self._task_vars = task_vars
        return self._call()
