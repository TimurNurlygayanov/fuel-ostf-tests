#    Copyright 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import logging

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from pecan import rest, expose, request
from fuel_plugin.ostf_adapter.storage import models


LOG = logging.getLogger(__name__)


class BaseRestController(rest.RestController):
    def _handle_get(self, method, remainder):
        if len(remainder):
            method_name = remainder[0]
            if method.upper() in self._custom_actions.get(method_name, []):
                controller = self._find_controller(
                    'get_%s' % method_name,
                    method_name
                )
                if controller:
                    return controller, remainder[1:]
        return super(BaseRestController, self)._handle_get(method, remainder)


class TestsController(BaseRestController):

    @expose('json')
    def get_one(self, test_name):
        raise NotImplementedError()

    @expose('json')
    def get_all(self):
        with request.session.begin(subtransactions=True):
            tests = request.session.query(models.Test)\
                .filter_by(test_run_id=None)\
                .all()

            return [item.frontend for item in tests]


class TestsetsController(BaseRestController):

    @expose('json')
    def get_one(self, test_set):
        with request.session.begin(subtransactions=True):
            test_set = request.session.query(models.TestSet)\
                .filter_by(id=test_set).first()
            if test_set and isinstance(test_set, models.TestSet):
                return test_set.frontend
            return {}

    @expose('json')
    def get_all(self):
        with request.session.begin(subtransactions=True):
            return [item.frontend for item
                    in request.session.query(models.TestSet).all()]


class TestrunsController(BaseRestController):

    _custom_actions = {
        'last': ['GET'],
    }

    @expose('json')
    def get_all(self):
        with request.session.begin(subtransactions=True):
            return [item.frontend for item
                    in request.session.query(models.TestRun).all()]

    @expose('json')
    def get_one(self, test_run_id):
        with request.session.begin(subtransactions=True):
            test_run = request.session.query(models.TestRun)\
                .filter_by(id=test_run_id).first()
            if test_run and isinstance(test_run, models.TestRun):
                return test_run.frontend
            return {}

    @expose('json')
    def get_last(self, cluster_id):
        with request.session.begin(subtransactions=True):
            test_run_ids = request.session.query(func.max(models.TestRun.id)) \
                .group_by(models.TestRun.test_set_id).\
                filter_by(cluster_id=cluster_id)
            test_runs = request.session.query(models.TestRun). \
                options(joinedload('tests')). \
                filter(models.TestRun.id.in_(test_run_ids))
            return [item.frontend for item in test_runs]

    @expose('json')
    def post(self):
        test_runs = json.loads(request.body)
        res = []
        with request.session.begin(subtransactions=True):
            for test_run in test_runs:
                test_set = test_run['testset']
                metadata = test_run['metadata']
                tests = test_run.get('tests', [])

                test_set = models.TestSet.get_test_set(
                    request.session, test_set)
                test_run = models.TestRun.start(
                    request.session, test_set, metadata, tests)
                res.append(test_run)
        return res

    @expose('json')
    def put(self):
        test_runs = json.loads(request.body)
        data = []
        with request.session.begin(subtransactions=True):
            for test_run in test_runs:
                status = test_run.get('status')
                tests = test_run.get('tests', [])
                test_run = models.TestRun.get_test_run(request.session,
                                                       test_run['id'])
                if status == 'stopped':
                    data.append(test_run.stop(request.session))
                elif status == 'restarted':
                    data.append(test_run.restart(request.session, tests=tests))
        return data
