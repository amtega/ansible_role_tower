#!/usr/bin/python
# Make coding more python3-ish, this is required for contributions to Ansible
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    def get_var(self, task_vars, name, default=None):
        """Return a variable expanded"""

        if name in task_vars:
            ret = self._templar.template(task_vars.get(name))
        else:
            ret = default

        return ret

    def run(self, tmp=None, task_vars=None):
        """Run the action plugin"""

        super(ActionModule, self).run(tmp, task_vars)

        try:
            tower_host = self.get_var(task_vars, "tower_host", None)
            tower_username = self.get_var(task_vars, "tower_username", None)
            tower_password = self.get_var(task_vars, "tower_password", None)
            validate_certs = self.get_var(task_vars, "validate_certs", True)
            tower_token = self.get_var(task_vars, "tower_token", None)
            tower_token_cleanup = self.get_var(task_vars,
                                               "tower_token_cleanup",
                                               False)

            # If token fact is already defined use it

            if not tower_token_cleanup and tower_token is not None:
                token = tower_token
            elif not tower_token_cleanup \
                    and "ansible_facts" in task_vars \
                    and "tower_token" in task_vars["ansible_facts"]:
                token = task_vars["ansible_facts"]["tower_token"]
            elif not tower_token_cleanup \
                and "ansible_local" in task_vars \
                    and "tower" in task_vars["ansible_local"] \
                    and "token" in task_vars["ansible_local"]["tower"]:
                token = task_vars["ansible_local"]["tower"]["token"]
            else:
                login_url = "{host}/api/login/".format(host=tower_host)
                tokens_url = "{host}/api/v2/tokens/".format(host=tower_host)

                # Get CSFR token

                uri_args = dict(
                    url=login_url,
                    method="GET",
                    validate_certs=validate_certs,
                    status_code=201,
                    return_content=True
                )

                uri_result = self._execute_module(module_name='uri',
                                                  module_args=uri_args,
                                                  task_vars=task_vars,
                                                  tmp=tmp)

                csrftoken = uri_result["cookies"]["csrftoken"]
                cookie = uri_result["cookies_string"]

                # Login into api rest

                uri_args = dict(
                    url=login_url,
                    method="POST",
                    headers={"Referer": login_url,
                             "X-CSRFToken": csrftoken,
                             "Cookie": cookie},
                    body_format="form-urlencoded",
                    body={"username": tower_username,
                          "password": tower_password,
                          "next": "/api"},
                    validate_certs=validate_certs,
                    status_code=200,
                    return_content=True,
                    follow_redirects="all",
                )

                uri_result = self._execute_module(module_name='uri',
                                                  module_args=uri_args,
                                                  task_vars=task_vars,
                                                  tmp=tmp)

                cookie = uri_result["cookies_string"]

                # Cleanup tokens

                if tower_token_cleanup:
                    more_tokens = True
                    while more_tokens:
                        uri_args = dict(
                            url=tokens_url + "?page_size=200",
                            method="GET",
                            headers={"X-CSRFToken": csrftoken,
                                     "Cookie": cookie},
                            body_format="json",
                            validate_certs=validate_certs,
                            status_code=201,
                            return_content=True
                        )

                        token_list_uri_result = self._execute_module(
                                                          module_name='uri',
                                                          module_args=uri_args,
                                                          task_vars=task_vars,
                                                          tmp=tmp)

                        for token in token_list_uri_result["json"]["results"]:
                            uri_args = dict(
                                url=tokens_url + str(token["id"]) + "/",
                                method="DELETE",
                                headers={"X-CSRFToken": csrftoken,
                                         "Cookie": cookie},
                                body_format="json",
                                validate_certs=validate_certs,
                                status_code=204,
                                return_content=True
                            )

                            uri_result = self._execute_module(
                                                        module_name='uri',
                                                        module_args=uri_args,
                                                        task_vars=task_vars,
                                                        tmp=tmp)

                        if "next" in token_list_uri_result["json"]:
                            tokens_url = "{host}{next}".format(
                                    host=tower_host,
                                    next=token_list_uri_result["json"]["next"])
                        else:
                            more_tokens = False

                # Create tokens

                uri_args = dict(
                    url=tokens_url,
                    method="POST",
                    headers={"X-CSRFToken": csrftoken,
                             "Cookie": cookie},
                    validate_certs=validate_certs,
                    status_code=201,
                    return_content=True
                )

                uri_result = self._execute_module(module_name='uri',
                                                  module_args=uri_args,
                                                  task_vars=task_vars,
                                                  tmp=tmp)

                token = uri_result["json"]["token"]

        except Exception as e:
            return dict(
                failed=True,
                msg="Operation in {0} failed: {1} / {2}".format(uri_result["url"],
                                                                e,
                                                                uri_result))
        finally:
            self._remove_tmp_path(self._connection._shell.tmpdir)

        return dict(ansible_facts=dict(tower_token=token))
        self._remove_tmp_path(self._connection._shell.tmpdir)

        return dict(ansible_facts=dict(tower_token=token))
