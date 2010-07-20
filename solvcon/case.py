# -*- coding: UTF-8 -*-
# Copyright (C) 2008-2010 by Yung-Yu Chen.  See LICENSE.txt for terms of usage.

"""
Simulation cases.
"""

from .gendata import SingleAssignDict, AttributeDict

class ArrangementRegistry(SingleAssignDict, AttributeDict):
    """
    Arrangement registry class.  A simulation is a callable that returns a case
    object.
    """
    def __setitem__(self, key, value):
        assert callable(value)
        super(ArrangementRegistry, self).__setitem__(key, value)
arrangements = ArrangementRegistry()  # overall registry singleton.

class CaseInfoMeta(type):
    """
    Meta class for case information class.
    """
    def __new__(cls, name, bases, namespace):
        newcls = super(CaseInfoMeta, cls).__new__(cls, name, bases, namespace)
        # incremental modification of defdict.
        defdict = {}
        for base in bases:
            defdict.update(getattr(base, 'defdict', {}))
        defdict.update(newcls.defdict)
        newcls.defdict = defdict
        # create different simulation registry objects for case classes.
        newcls.arrangements = ArrangementRegistry()
        return newcls
class CaseInfo(dict):
    """
    Generic case information abstract class.  It's the base class that all case
    information classes should subclass, to form hierarchical information 
    object.
    """
    __metaclass__ = CaseInfoMeta
    defdict = {}
    def __getattr__(self, name):
        """
        Consult self dictionary for attribute.  It's a shorthand.
        """
        if name == '__setstate__':
            raise AttributeError
        return self[name]
    def __setattr__(self, name, value):
        """
        Save to self dictionary first, then self object table.

        @note: This method is overriden as a stupid-preventer.  It makes
        attribute setting consistent with attribute getting.
        """
        if name in self:
            self[name] = value
        else:
            super(CaseInfo, self).__setattr__(name, value)
    def _set_through(self, key, val):
        """
        Set to self with the dot-separated key.
        """
        tokens = key.split('.', 1)
        fkey = tokens[0]
        if len(tokens) == 2:
            self[fkey]._set_through(tokens[1], val)
        else:
            self[fkey] = val
    def __init__(self, _defdict=None, *args, **kw):
        """
        Assign default values to self after initiated.

        @keyword _defdict: customized defdict; internal use only.
        @type _defdict: dict
        """
        super(CaseInfo, self).__init__(*args, **kw)
        # customize defdict.
        if _defdict is None:
            defdict = self.defdict
        else:
            defdict = dict(self.defdict)
            defdict.update(_defdict)
        # parse first hierarchy to form key groups.
        keygrp = dict()
        for key in defdict.keys():
            if key is None or key == '':
                continue
            tokens = key.split('.', 1)
            if len(tokens) == 2:
                fkey, rkey = tokens
                keygrp.setdefault(fkey, dict())[rkey] = defdict[key]
            else:
                fkey = tokens[0]
                keygrp[fkey] = defdict[fkey]
        # set up first layer keys recursively.
        for fkey in keygrp.keys():
            data = keygrp[fkey]
            if isinstance(data, dict):
                self[fkey] = CaseInfo(_defdict=data)
            elif isinstance(data, type):
                try:
                    self[fkey] = data()
                except TypeError:
                    self[fkey] = data
            else:
                self[fkey] = data

class BaseCase(CaseInfo):
    """
    Base class for simulation cases.

    init() and run() are the two primary methods responsible for the
    execution of the simulation case object.  Both methods accept a keyword
    parameter ``level'' which indicates the run level of the run:
      - run level 0: fresh run (default),
      - run level 1: restart run,
      - run level 2: initialization only.

    @ivar runhooks: a special list containing all the hook objects to be run.
    @itype runhooks: solvcon.hook.HookList
    """

    CSEFN_DEFAULT = 'solvcon.dump.case.obj'

    from . import conf, batch
    defdict = {
        # execution related.
        'execution.fpdtype': conf.env.fpdtypestr,
        'execution.scheduler': batch.Scheduler,
        'execution.resources': dict,    # for scheduler.
        'execution.stop': False,
        'execution.time': 0.0,
        'execution.time_increment': 0.0,
        'execution.step_init': 0,
        'execution.step_current': None,
        'execution.steps_run': None,
        'execution.steps_stride': 1,
        'execution.cCFL': 0.0,  # current.
        'execution.aCFL': 0.0,  # accumulated.
        'execution.mCFL': 0.0,  # mean.
        'execution.neq': 0, # number of unknowns.
        'execution.var': dict,  # for Calculator hooks.
        'execution.varstep': None,  # the step for which var and dvar are valid.
        'execution.ncore': -1,  # number of cores to use in solver.
        # dynamic related.
        'dynamic.inputfn': 'solvcon.input',
        'dynamic.bakfn': 'solvcon.input.bak',
        'dynamic.preserve': False,
        # io related.
        'io.abspath': False,    # flag to use abspath or not.
        'io.rootdir': None,
        'io.basedir': None,
        'io.basefn': None,
        'io.empty_jobdir': False,
        'io.solver_output': False,
        # conditions.
        'condition.mtrllist': list,
        # solver.
        'solver.solvertype': None,
        'solver.solverobj': None,
        # logging.
        'log.time': dict,
    }
    del conf, batch
    from .helper import info

    def _log_start(self, action, msg='', postmsg=' ... '):
        """
        Print to user and record start time for certain action.

        @param action: action key.
        @type action: str
        @keyword msg: trailing message for the action key.
        @type msg: str
        @return: nothing.
        """
        from time import time
        info = self.info
        tarr = [0,0,0]
        tarr[0] = time()
        self.log.time[action] = tarr
        info(
            info.prefix * (info.width-info.level*info.nchar),
            travel=1
        )
        info('\nStart %s%s%s' % (action, msg, postmsg))
        info(
            '\n' + info.prefix * (info.width-info.level*info.nchar) + '\n',
        )

    def _log_end(self, action, msg='', postmsg=' . '):
        """
        Print to user and record end time for certain action.

        @param action: action key.
        @type action: str
        @keyword msg: supplemental message.
        @type msg: str
        @return: nothing
        """
        from time import time
        info = self.info
        tarr = self.log.time.setdefault(action, [0,0,0])
        tarr[1] = time()
        tarr[2] = tarr[1] - tarr[0]
        info(
            info.prefix * (info.width-info.level*info.nchar) + \
            '\nEnd %s%s%sElapsed time (sec) = %g' % (
                action, msg, postmsg, tarr[2]
            )
        )
        info(
            '\n' + info.prefix * (info.width-(info.level-1)*info.nchar) + '\n',
            travel=-1
        )

    def __init__(self, **kw):
        """
        Initiailize the basic case.  Set through keyword parameters.
        """
        import os
        from .hook import HookList
        # populate value from keywords.
        initpairs = list()
        for cinfok in self.defdict.keys():
            lkey = cinfok.split('.')[-1]
            initpairs.append((cinfok, kw.pop(lkey, None)))
        # initialize with the left keywords.
        super(BaseCase, self).__init__(**kw)
        # populate value from keywords.
        for cinfok, val in initpairs:
            if val is not None:
                self._set_through(cinfok, val)
        # create runhooks.
        self.runhooks = HookList(self)
        # expand basedir.
        if self.io.abspath:
            self.io.basedir = os.path.abspath(self.io.basedir)

    def _dynamic_execute(self):
        """
        Dynamically execute the codes stored in the input file specified by
        the case.

        @return: nothing
        """
        import os
        import traceback
        from cStringIO import StringIO
        if not self.dynamic.inputfn: return
        try:
            # load codes.
            if os.path.exists(self.dynamic.inputfn):
                f = open(self.dynamic.inputfn, 'r')
                codes = f.read()
                f.close()
            else:
                codes = ''
            if codes.strip():
                # clear/preserve code file.
                f = open(self.dynamic.inputfn, 'w')
                if self.dynamic.preserve:
                    f.write(codes)
                f.close()
                # backup codes.
                f = open(self.dynamic.bakfn, 'a')
                f.write('\n### %s step %d/%d\n' % (self.io.basefn,
                    self.execution.step_current, self.execution.steps_run,
                ))
                f.write(codes)
                f.close()
                # run codes.
                exec(codes)
        except Exception, e:
            f = StringIO()
            f.write('\n@@@ dynamic execution at step %d @@@' %
                self.execution.step_current)
            f.write('\nCode:\n %s\n' % codes)
            traceback.print_exc(file=f)
            self.info(f.getvalue())
            f.close()
        # reset preservation flag.
        self.dynamic.preserve = False

    def init(self, level=0):
        """
        Initialize solver.  Nothing inside now.

        @keyword level: run level; higher level does less work.
        @type level: int

        @return: nothing.
        """
        pass

    def run(self, level=0):
        """
        Run the simulation case; time marching.

        @keyword level: run level; higher level does less work.
        @type level: int

        @return: nothing.
        """
        # start log.
        self._log_start('run', msg=' '+self.io.basefn)
        self.info("\n")
        # prepare for time marching.
        aCFL = 0.0
        self.execution.step_current = 0
        self.runhooks('preloop')
        self._log_start('loop_march')
        while self.execution.step_current < self.execution.steps_run:
            self.runhooks('premarch')
            cCFL = self.solver.solverobj.march(
                self.execution.step_current*self.execution.time_increment,
                self.execution.time_increment)
            # process CFL.
            istep = self.execution.step_current
            aCFL += cCFL
            mCFL = aCFL/(istep+1)
            self.execution.cCFL = cCFL
            self.execution.aCFL = aCFL
            self.execution.mCFL = mCFL
            # increment to next time step.
            self.execution.step_current += 1
            self.runhooks('postmarch')
        self._log_start('loop_march')
        self.runhooks('postloop')
        # end log.
        self._log_end('run')

    def cleanup(self, signum=None, frame=None):
        import signal
        if signum == signal.SIGINT:
            raise KeyboardInterrupt

    @classmethod
    def register_arrangement(cls, func):
        """
        Decorate simulation functions.  This function asserts required
        signature which is necessary for a function to be a valid simulation
        function.  Moreover, all the simulation function should be decorated by
        this decorator.

        @return: simulation function.
        @rtype: callable
        """
        import signal
        import cPickle as pickle
        from .batch import Scheduler
        def simu(*args, **kw):
            kw.pop('casename', None)
            resources = kw.pop('resources', dict())
            scheduler = kw.get('scheduler', Scheduler)
            submit = kw.pop('submit')
            postpone = kw.pop('postpone', False)
            runlevel = kw.pop('runlevel')
            # obtain the case object.
            if runlevel == 1:
                case = pickle.load(open(cls.CSEFN_DEFAULT, 'rb'))
            else:
                casename = func.__name__
                case = func(casename=casename, *args, **kw)
            # submit/run.
            try:
                if submit:
                    sbm = scheduler(case, arnname=casename, **resources)
                    sbm(runlevel=runlevel, postpone=postpone)
                else:
                    signal.signal(signal.SIGTERM, case.cleanup)
                    signal.signal(signal.SIGINT, case.cleanup)
                    case.init(level=runlevel)
                    case.info('\n')
                    case.run(level=runlevel)
                    case.cleanup()
            except:
                case.cleanup()
                raise
        # register self to simulation registries.
        cls.arrangements[func.__name__] = simu
        arrangements[func.__name__] = simu
        return simu

class BlockCase(BaseCase):
    """
    Base class for multi-dimensional cases using block.

    Subclass must implement _load_block_for_init() private method for init()
    method to load the needed block.

    @ivar pythonpaths: extra python paths.
    @itype pythonpaths: list
    """
    defdict = {
        # execution related.
        'execution.npart': None,    # number of decomposed blocks.
        'execution.step_restart': None,
        'execution.steps_dump': None,
        # IO.
        'io.meshfn': None,
        'io.rkillfn': 'solvcon.kill.sh',
        'io.dump.csefn': 'solvcon.dump.case.obj',
        'io.dump.svrfntmpl': 'solvcon.dump.solver%s.obj',
        # conditions.
        'condition.bcmap': dict,
        # solver.
        'solver.domaintype': None,
        'solver.domainobj': None,
        'solver.dealer': None,
        'solver.outposts': list,
        'solver.envar': dict,
        'solver.ibcthread': False,
    }

    def __init__(self, **kw):
        self.pythonpaths = kw.pop('pythonpaths', [])
        super(BlockCase, self).__init__(**kw)

    @property
    def is_parallel(self):
        """
        Determine if self should do parallel or not.

        @return: 0 means sequential; 1 means local parallel.
        @rtype: int
        """
        from . import domain
        domaintype = self.solver.domaintype
        if domaintype == domain.Domain:
            assert self.execution.npart == None
            flag_parallel = 0 # means sequential.
        elif domaintype == domain.Collective:
            assert isinstance(self.execution.npart, int)
            flag_parallel = 1 # means local parallel.
        elif domaintype == domain.Distributed:
            assert isinstance(self.execution.npart, int)
            flag_parallel = 2 # means network parallel.
        else:
            raise TypeError, 'domaintype shouldn\'t be %s' % domaintype
        return flag_parallel

    def dump(self):
        """
        Dump case and remote solver objects for later restart.

        @return: nothing
        """
        import cPickle as pickle
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        # record the step can be restarted from.
        self.execution.step_restart = self.execution.step_current
        # unbind.
        if flag_parallel:
            for iblk in range(len(self.solver.domainobj)):
                dealer[iblk].cmd.dump(self.io.dump.svrfntmpl % str(iblk))
            outposts = self.solver.outposts
        else:
            self.solver.domainobj.unbind()
            self.solver.solverobj.unbind()
            svrholds = dict()
            for key in ['mesg',]:
                svrholds[key] = getattr(self.solver.solverobj, key)
                setattr(self.solver.solverobj, key, None)
        # pickle.
        self.solver.dealer = None
        self.solver.outposts = list()
        pickle.dump(self, open(self.io.dump.csefn, 'wb'),
            pickle.HIGHEST_PROTOCOL)
        # bind.
        if flag_parallel:
            self.solver.outposts = outposts
            self.solver.dealer = dealer
        else:
            for key in svrholds:
                setattr(self.solver.solverobj, key, svrholds[key])
            self.solver.solverobj.bind()
            self.solver.domainobj.bind()

    def cleanup(self, signum=None, frame=None):
        if self.solver.solverobj != None:
            self.solver.solverobj.unbind()
        for ftw in self.solver.outposts: ftw.kill_remote()
        super(BlockCase, self).cleanup(signum=signum, frame=frame)

    ############################################################################
    ###
    ### Begin of block of case initialization logics.
    ###
    ############################################################################

    def init(self, level=0):
        """
        Load block and initialize solver from the geometry information in the
        block and conditions in the self case.  If parallel run is specified
        (through domaintype), split the domain and perform corresponding tasks.
        """
        from .boundcond import interface
        self._log_start('init', msg=' (level %d) %s' % (level, self.io.basefn))
        # initilize the whole solver and domain.
        if level != 1:
            self._log_start('build_domain')
            self.solver.domainobj = self.solver.domaintype(self.load_block())
            self._log_end('build_domain')
        # for serial execution.
        if not self.is_parallel:
            # create and initialize solver.
            if level != 1:
                self._local_init_solver()
            else:
                self._local_bind_solver()
        # for parallel execution.
        else:
            # split the domain.
            if level != 1:
                self.info('\n')
                self._log_start('split_domain')
                self.solver.domainobj.split(
                    nblk=self.execution.npart, interface_type=interface)
                self._log_end('split_domain')
            # make dealer and create workers for the dealer.
            self.info('\n')
            self._log_start('build_dealer')
            self.solver.dealer = self._create_workers()
            self._log_end('build_dealer')
            # make interconnections for rpc.
            self.info('\n')
            self._log_start('interconnect')
            self._interconnect()
            self._log_end('interconnect')
            # spread out and initialize decomposed solvers.
            if level != 1:
                self.info('\n')
                self._log_start('remote_init_solver')
                self._remote_init_solver()
                self._log_end('remote_init_solver')
            else:
                self.info('\n')
                self._log_start('remote_load_solver')
                self._remote_load_solver()
                self._log_end('remote_load_solver')
            # exchange boundary information.
            self.info('\n')
            self._log_start('exchange')
            self._exchange_meta()
            self._log_end('exchange')
            # initialize exchange for remote solver objects.
            if level != 1:
                self.info('\n')
                self._log_start('exchange_metric')
                self._exchange_metric()
                self._log_end('exchange_metric')
        self._log_end('init', msg=' '+self.io.basefn)

    def load_block(self):
        """
        Return a block for init.

        @return: a block object.
        @rtype: solvcon.block.Block
        """
        import gzip
        from .io.gambit import GambitNeutral
        from .io.block import BlockIO
        meshfn = self.io.meshfn
        bcmapper = self.condition.bcmap
        if '.neu' in meshfn:
            self._log_start('read_neu_data', msg=' from %s'%meshfn)
            if meshfn.endswith('.gz'):
                stream = gzip.open(meshfn)
            else:
                stream = open(meshfn)
            data = stream.read()
            stream.close()
            self._log_end('read_neu_data')
            self._log_start('create_neu_object')
            neu = GambitNeutral(data)
            self._log_end('create_neu_object')
            self._log_start('convert_neu_to_block')
            blk = neu.toblock(bcname_mapper=bcmapper)
            self._log_end('convert_neu_to_block')
        elif '.blk' in meshfn:
            self._log_start('load_block')
            blk = BlockIO().load(stream=meshfn, bcmapper=bcmapper)
            self._log_end('load_block')
        else:
            raise ValueError
        return blk

    # solver object initialization/binding/loading.
    def _local_init_solver(self):
        """
        @return: nothing
        """
        svr = self.solver.solvertype(self.solver.domainobj.blk,
            ncore=self.execution.ncore,
            neq=self.execution.neq, fpdtype=self.execution.fpdtype,
            enable_mesg=self.io.solver_output,
        )
        self.runhooks.drop_anchor(svr)
        svr.bind()
        svr.ibcthread = self.solver.ibcthread
        svr.init()
        self.solver.solverobj = svr
    def _local_bind_solver(self):
        """
        @return: nothing
        """
        self.solver.solverobj.bind()
        self.solver.solverobj.ibcthread = self.solver.ibcthread
        self.solver.domainobj.bind()
    def _remote_init_solver(self):
        """
        @return: nothing
        """
        dealer = self.solver.dealer
        nblk = len(self.solver.domainobj)
        for iblk in range(nblk):
            sbk = self.solver.domainobj[iblk]
            self.info('solver #%d/%d: ' % (iblk+1, nblk))
            svr = self.solver.solvertype(sbk,
                ncore=self.execution.ncore,
                neq=self.execution.neq, fpdtype=self.execution.fpdtype,
                enable_mesg=self.io.solver_output,
            )
            self.info('sending ... ')
            svr.svrn = iblk
            svr.nsvr = nblk
            self.runhooks.drop_anchor(svr)
            svr.unbind()    # ensure no pointers (unpicklable) in solver.
            dealer[iblk].remote_setattr('muscle', svr)
            self.info('done.\n')
        self.info('Bind/Init ... ')
        for sdw in dealer: sdw.cmd.bind()
        for sdw in dealer: sdw.cmd.remote_setattr('ibcthread',
            self.solver.ibcthread)
        for sdw in dealer: sdw.cmd.init()
        dealer.barrier()
        self.info('done.\n')
    def _remote_load_solver(self):
        """
        @return: nothing
        """
        dealer = self.solver.dealer
        nblk = len(self.solver.domainobj)
        for iblk in range(nblk):
            dealer[iblk].remote_loadobj('muscle',
                self.io.dump.svrfntmpl % str(iblk))
        for sdw in dealer: sdw.cmd.bind()
        for sdw in dealer: sdw.cmd.remote_setattr('ibcthread',
            self.solver.ibcthread)
        dealer.barrier()

    # workers and worker manager (dealer) creation.
    def _create_workers(self):
        """
        Make dealer and create workers for the dealer.

        @return: worker manager.
        @rtype: solvcon.rpc.Dealer
        """
        from .rpc import Dealer
        nblk = len(self.solver.domainobj)
        flag_parallel = self.is_parallel
        if flag_parallel == 1:
            family = None
            create_workers = self._create_workers_local
        elif flag_parallel == 2:
            family = 'AF_INET'
            create_workers = self._create_workers_remote
        dealer = Dealer(family=family)
        create_workers(dealer, nblk)
        return dealer
    def _get_profiler_data(self, iblk):
        from .conf import env
        if env.command != None:
            ops, args = env.command.opargs
            if getattr(ops, 'use_profiler'):
                return (
                    ops.profiler_dat+'%d'%iblk,
                    ops.profiler_log+'%d'%iblk,
                    ops.profiler_sort,
                )
        return None
    def _create_workers_local(self, dealer, nblk):
        from .rpc import Worker
        for iblk in range(nblk):
            dealer.hire(Worker(None,
                profiler_data=self._get_profiler_data(iblk)))
    def _create_workers_remote(self, dealer, nblk):
        import os, sys
        from .rpc import DEFAULT_AUTHKEY, Footway, Shadow
        from .conf import env
        info = self.info
        authkey = DEFAULT_AUTHKEY
        paths = dict([(key, os.environ.get(key, '').split(':')) for key in
            'LD_LIBRARY_PATH',
            'PYTHONPATH',
        ])
        paths['PYTHONPATH'].extend(self.pythonpaths)
        paths['PYTHONPATH'].insert(0, self.io.rootdir)
        # prepare nodelist.
        info('\n********\nNodelist')
        nodelist = self.execution.scheduler(self).nodelist()
        if env.command != None and env.command.opargs[0].compress_nodelist:
            info(' (compressed)')
        info(':\n')
        for node in nodelist:
            info('  %s\n' % node.name)
        # print out content of node file.
        iworker = 0 
        for node in nodelist:
            inetaddr = node.address
            port = Footway.build_outpost(inetaddr,
                authkey=authkey, envar=self.solver.envar, paths=paths)
            ftw = Footway(address=(inetaddr, port), authkey=authkey)
            ftw.chdir(os.getcwd())
            self.solver.outposts.append(ftw)
            for iblk in range(node.ncore):
                pport = ftw.create(
                    profiler_data=self._get_profiler_data(iworker))
                dealer.appoint(inetaddr, pport, authkey)
                iworker += 1
        assert len(dealer) == nblk
        # create remote killer script.
        f = open(self.io.rkillfn, 'w')
        f.write("""#!/bin/sh
nodes="
%s
"
for node in $nodes; do rsh $node killall %s; done
""" % (
            '\n'.join([node.name for node in nodelist]),
            os.path.split(sys.executable)[-1],
        ))

    # interconnection.
    def _interconnect(self):
        """
        Make interconnections for distributed solver objects.

        @return: nothing
        """
        dom = self.solver.domainobj
        dealer = self.solver.dealer
        nblk = len(dom)
        for iblk in range(nblk):
            for jblk in range(nblk):
                if iblk >= jblk:
                    continue
                if dom.interfaces[iblk][jblk] != None:
                    dealer.bridge((iblk, jblk))
        dealer.barrier()
        # show exchanging pairs.
        self.info('Interface exchanging pairs:\n')
        dwidth = len(str(nblk-1))
        ifacelists = dom.ifacelists
        for iblk in range(nblk):
            ifacelist = ifacelists[iblk]
            sdw = dealer[iblk]
            # print.
            self.info(('%%0%dd ->' % dwidth) % iblk)
            for pair in ifacelist:
                if pair < 0:
                    stab = '-' * (2*dwidth+1)
                else:
                    stab = '-'.join([('%%0%dd'%dwidth)%item for item in pair])
                self.info(' %s' % stab)
            self.info('\n')
        # construct spanning tree.
        #graph = list()
        #for iblk in range(nblk):
        #    ifacelist = ifacelists[iblk]
        #    lst = list()
        #    for pair in ifacelist:
        #        if isinstance(pair, tuple):
        #            lst.append(pair[0] + pair[1] - iblk)
        #    graph.append(lst)
        #dealer.span(graph)

    # exchange
    def _exchange_meta(self):
        """
        Exchange meta data.

        @return: nothing
        """
        dom = self.solver.domainobj
        dealer = self.solver.dealer
        nblk = len(dom)
        self.info('Interface exchanging pairs:\n')
        dwidth = len(str(nblk-1))
        ifacelists = dom.ifacelists
        for iblk in range(nblk):
            ifacelist = ifacelists[iblk]
            sdw = dealer[iblk]
            sdw.cmd.init_exchange(ifacelist)
            self.info('BCs for solver #%d/%d initialized.\n' % (iblk+1, nblk))
    def _exchange_metric(self):
        """
        Exchange metric data for solver.

        @return: nothing
        """
        dealer = self.solver.dealer
        for arrname in self.solver.solvertype._interface_init_:
            for sdw in dealer: sdw.cmd.exchangeibc(arrname,
                with_worker=True)

    ############################################################################
    ###
    ### End of block of case initialization logics.
    ###
    ############################################################################

    ############################################################################
    ###
    ### Begin of block of case execution.
    ###
    ############################################################################

    def run(self, level=0):
        """
        Run the simulation case; time marching.

        @keyword level: run level; higher level does less work.
        @type level: int

        @return: nothing.
        """
        self._log_start('run', msg=' (level %d) %s' % (level, self.io.basefn))
        self.execution.step_current = self.execution.step_init
        if level < 1:
            self._run_provide()
            self._run_preloop()
        if level < 2:
            self._run_march()
            self._run_postloop()
            self._run_exhaust()
        else:   # level == 2.
            self.dump()
        self._run_final()
        self._log_end('run', msg=' '+self.io.basefn)

    # logics before entering main loop (march).
    def _run_provide(self):
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        # anchor: provide.
        if flag_parallel:
            for sdw in dealer: sdw.cmd.provide()
        else:
            self.solver.solverobj.provide()
    def _run_preloop(self):
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        # hook: preloop.
        self.runhooks('preloop')
        if flag_parallel:
            for sdw in dealer: sdw.cmd.preloop()
            for sdw in dealer: sdw.cmd.exchangeibc('soln', with_worker=True)
            for sdw in dealer: sdw.cmd.exchangeibc('dsoln', with_worker=True)
            for sdw in dealer: sdw.cmd.boundcond()
        else:
            self.solver.solverobj.preloop()
            self.solver.solverobj.boundcond()

    def _run_march(self):
        from time import time as timer
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        self.log.time['solver_march'] = 0.0
        aCFL = 0.0
        self.info('\n')
        self._log_start('loop_march')
        while self.execution.step_current < self.execution.steps_run:
            # the first thing is detecting for dynamic codes.
            self._dynamic_execute()
            if self.execution.stop: break
            # dump before hooks.
            if self.execution.steps_dump != None and \
               self.execution.step_current != self.execution.step_restart and \
               self.execution.step_current%self.execution.steps_dump == 0:
                self.dump()
            # hook: premarch.
            self.runhooks('premarch')
            # march.
            solver_march_marker = timer()
            cCFL = -1.0
            steps_stride = self.execution.steps_stride
            time_increment = self.execution.time_increment
            time = self.execution.step_current*time_increment
            if flag_parallel:
                for sdw in dealer: sdw.cmd.march(time, time_increment,
                    steps_stride, with_worker=True)
                cCFL = max([sdw.recv() for sdw in dealer])
            else:
                cCFL = self.solver.solverobj.march(time, time_increment,
                    steps_stride)
            self.execution.time += time_increment*steps_stride
            self.log.time['solver_march'] += timer() - solver_march_marker
            # process CFL.
            istep = self.execution.step_current
            aCFL += cCFL*steps_stride
            mCFL = aCFL/(istep+steps_stride)
            self.execution.cCFL = cCFL
            self.execution.aCFL = aCFL
            self.execution.mCFL = mCFL
            # increment to next time step.
            self.execution.step_current += steps_stride
            # hook: postmarch.
            self.runhooks('postmarch')
        # end log.
        self._log_end('loop_march')
        self.info('\n')

    # logics after exiting main loop (march).
    def _run_postloop(self):
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        # hook: postloop.
        if flag_parallel:
            for sdw in dealer: sdw.cmd.postloop()
        else:
            self.solver.solverobj.postloop()
        self.runhooks('postloop')
    def _run_exhaust(self):
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        # anchor: exhaust.
        if flag_parallel:
            for sdw in dealer: sdw.cmd.exhaust()
        else:
            self.solver.solverobj.exhaust()
    def _run_final(self):
        dealer = self.solver.dealer
        flag_parallel = self.is_parallel
        # finalize.
        if flag_parallel:
            for sdw in dealer: sdw.cmd.final()
            self.solver.dealer.terminate()
            for ftw in self.solver.outposts: ftw.terminate()
        else:
            self.solver.solverobj.final()

    ############################################################################
    ###
    ### End of block of case execution.
    ###
    ############################################################################
