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

        # If token fact is already defined use it

        if "ansible_facts" in task_vars \
           and "tower_token" in task_vars["ansible_facts"]:
            token = task_vars["ansible_facts"]["tower_token"]
        else:
            tower_host = self.get_var(task_vars, "tower_host", None)
            tower_username = self.get_var(task_vars, "tower_username", None)
            tower_password = self.get_var(task_vars, "tower_password", None)
            validate_certs = self.get_var(task_vars, "validate_certs", True)

            uri_args = dict(
                url="{host}/api/v2/tokens/".format(host=tower_host),
                method="POST",
                user=tower_username,
                password=tower_password,
                validate_certs=validate_certs,
                force_basic_auth=True,
                status_code=201,
                return_content=True
            )

            uri_result = self._execute_module(module_name='uri',
                                              module_args=uri_args,
                                              task_vars=task_vars,
                                              tmp=tmp)

            token = uri_result["json"]["token"]

        return dict(ansible_facts=dict(tower_token=token))
