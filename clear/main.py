#! /usr/bin/python -u

import click
import os
import subprocess
from click_default_group import DefaultGroup
from natsort import natsorted
from swsssdk import ConfigDBConnector

try:
    # noinspection PyPep8Naming
    import ConfigParser as configparser
except ImportError:
    # noinspection PyUnresolvedReferences
    import configparser


# This is from the aliases example:
# https://github.com/pallets/click/blob/57c6f09611fc47ca80db0bd010f05998b3c0aa95/examples/aliases/aliases.py
class Config(object):
    """Object to hold CLI config"""

    def __init__(self):
        self.path = os.getcwd()
        self.aliases = {}

    def read_config(self, filename):
        parser = configparser.RawConfigParser()
        parser.read([filename])
        try:
            self.aliases.update(parser.items('aliases'))
        except configparser.NoSectionError:
            pass


# Global Config object
_config = None


# This aliased group has been modified from click examples to inherit from DefaultGroup instead of click.Group.
# DefaultFroup is a superclass of click.Group which calls a default subcommand instead of showing
# a help message if no subcommand is passed
class AliasedGroup(DefaultGroup):
    """This subclass of a DefaultGroup supports looking up aliases in a config
    file and with a bit of magic.
    """

    def get_command(self, ctx, cmd_name):
        global _config

        # If we haven't instantiated our global config, do it now and load current config
        if _config is None:
            _config = Config()

            # Load our config file
            cfg_file = os.path.join(os.path.dirname(__file__), 'aliases.ini')
            _config.read_config(cfg_file)

        # Try to get builtin commands as normal
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        # No builtin found. Look up an explicit command alias in the config
        if cmd_name in _config.aliases:
            actual_cmd = _config.aliases[cmd_name]
            return click.Group.get_command(self, ctx, actual_cmd)

        # Alternative option: if we did not find an explicit alias we
        # allow automatic abbreviation of the command.  "status" for
        # instance will match "st".  We only allow that however if
        # there is only one command.
        matches = [x for x in self.list_commands(ctx)
                   if x.lower().startswith(cmd_name.lower())]
        if not matches:
            # No command name matched. Issue Default command.
            ctx.arg0 = cmd_name
            cmd_name = self.default_cmd_name
            return DefaultGroup.get_command(self, ctx, cmd_name)
        elif len(matches) == 1:
            return DefaultGroup.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


# To be enhanced. Routing-stack information should be collected from a global
# location (configdb?), so that we prevent the continous execution of this
# bash oneliner. To be revisited once routing-stack info is tracked somewhere.
def get_routing_stack():
    command = "sudo docker ps | grep bgp | awk '{print$2}' | cut -d'-' -f3 | cut -d':' -f1"

    try:
        proc = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                shell=True,
                                stderr=subprocess.STDOUT)
        stdout = proc.communicate()[0]
        proc.wait()
        result = stdout.rstrip('\n')

    except OSError, e:
        raise OSError("Cannot detect routing-stack")

    return (result)


# Global Routing-Stack variable
routing_stack = get_routing_stack()


def run_command(command, pager=False, return_output=False):
    # Provide option for caller function to Process the output.
    proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    if return_output:
        return proc.communicate()
    elif pager:
        #click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        click.echo_via_pager(proc.stdout.read())
    else:
        #click.echo(click.style("Command: ", fg='cyan') + click.style(command, fg='green'))
        click.echo(proc.stdout.read())


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help', '-?'])


#
# 'cli' group (root group) ###
#

# This is our entrypoint - the main "Clear" command
@click.group(cls=AliasedGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """SONiC command line - 'Clear' command"""
    pass


#
# 'ip' group ###
#

# This allows us to add commands to both cli and ip groups, allowing for
# "Clear <command>" and "Clear ip <command>" to function the same
@cli.group()
def ip():
    """Clear IP """
    pass


# 'ipv6' group

@cli.group()
def ipv6():
    """Clear IPv6 information"""
    pass


#
# Inserting BGP functionality into cli's clear parse-chain.
# BGP commands are determined by the routing-stack being elected.
#
if routing_stack == "quagga":
    from .bgp_quagga_v4 import bgp
    ip.add_command(bgp)
    from .bgp_quagga_v6 import bgp
    ipv6.add_command(bgp)
elif routing_stack == "frr":
    from .bgp_quagga_v4 import bgp
    ip.add_command(bgp)
    from .bgp_frr_v6 import bgp
    ipv6.add_command(bgp)

@cli.command()
def counters():
    """Clear counters"""
    command = "portstat -c"
    run_command(command)

@cli.command()
@click.argument('interface', metavar='<interface_name>', required=False, type=str)
def rifcounters(interface):
    """Clear RIF counters"""
    command = "intfstat -c"
    if interface is not None:
        command = "intfstat -i {} -c".format(interface)
    run_command(command)

@cli.command()
def queuecounters():
    """Clear queue counters"""
    command = "queuestat -c"
    run_command(command)

@cli.command()
def pfccounters():
    """Clear pfc counters"""
    command = "pfcstat -c"
    run_command(command)

@cli.command()
def dropcounters():
    """Clear drop counters"""
    command = "dropstat -c clear"
    run_command(command)

#
# 'clear watermarks
#

@cli.group(name='priority-group')
def priority_group():
    """Clear priority_group WM"""
    pass

@priority_group.group()
def watermark():
    """Clear priority_group user WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@watermark.command('headroom')
def clear_wm_pg_headroom():
    """Clear user headroom WM for pg"""
    command = 'watermarkstat -c -t pg_headroom'
    run_command(command)

@watermark.command('shared')
def clear_wm_pg_shared():
    """Clear user shared WM for pg"""
    command = 'watermarkstat -c -t pg_shared'
    run_command(command)

@priority_group.group(name='persistent-watermark')
def persistent_watermark():
    """Clear queue persistent WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@persistent_watermark.command('headroom')
def clear_pwm_pg_headroom():
    """Clear persistent headroom WM for pg"""
    command = 'watermarkstat -c -p -t pg_headroom'
    run_command(command)

@persistent_watermark.command('shared')
def clear_pwm_pg_shared():
    """Clear persistent shared WM for pg"""
    command = 'watermarkstat -c -p -t pg_shared'
    run_command(command)

def interface_name_is_valid(interface_name):
    """Check if the interface name is valid
    """
    config_db = ConfigDBConnector()
    config_db.connect()
    port_dict = config_db.get_table('PORT')
    port_channel_dict = config_db.get_table('PORTCHANNEL')

    if interface_name is not None:
        if not port_dict:
            click.echo("port_dict is None!")
            raise click.Abort()
        for port_name in port_dict.keys():
            if interface_name == port_name:
                return True
        if port_channel_dict:
            for port_channel_name in port_channel_dict.keys():
                if interface_name == port_channel_name:
                    return True
    return False

@priority_group.command('threshold')
@click.argument('port_name', metavar='<port_name>', required=False)
@click.argument('pg_index', metavar='<pg_index>', required=False, type=int)
@click.argument('threshold_type', required=False, type=click.Choice(['shared', 'headroom']))
@click.pass_context
def threshold(ctx, port_name, pg_index, threshold_type):
    """ Clear priority group threshold """
    # If no params are provided, clear all priority-group entries.
    config_db = ConfigDBConnector()
    config_db.connect()

    all = False

    if port_name is None and pg_index is None and threshold_type is None:
        # clear all entries.
        key = 'priority-group'
        all = True
    elif port_name is None or pg_index is None or threshold_type is None:
        ctx.fail("port_name, pg_index and threshold_type are mandatory parameters.")
    else:
        if pg_index not in range(0, 8):
            ctx.fail("priority-group must be in range 0-7")
        if interface_name_is_valid(port_name) is False:
            ctx.fail("Interface name is invalid!!")
        key = 'priority-group' + '|' + threshold_type + '|' + port_name + '|' + str(pg_index)

    if all is True:
        entry_table = config_db.get_keys('THRESHOLD_TABLE')
        # Clear data for all keys
        for k in natsorted(entry_table):
            if k[0] == 'priority-group':
                config_db.set_entry('THRESHOLD_TABLE', k, None)
    else:
        entry = config_db.get_entry('THRESHOLD_TABLE', key)
        if entry:
            config_db.set_entry('THRESHOLD_TABLE', key, None)

@cli.group()
def queue():
    """Clear queue WM"""
    pass

@queue.group()
def watermark():
    """Clear queue user WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@watermark.command('unicast')
def clear_wm_q_uni():
    """Clear user WM for unicast queues"""
    command = 'watermarkstat -c -t q_shared_uni'
    run_command(command)

@watermark.command('multicast')
def clear_wm_q_multi():
    """Clear user WM for multicast queues"""
    command = 'watermarkstat -c -t q_shared_multi'
    run_command(command)

@queue.group(name='persistent-watermark')
def persistent_watermark():
    """Clear queue persistent WM. One does not simply clear WM, root is required"""
    if os.geteuid() != 0:
        exit("Root privileges are required for this operation")

@persistent_watermark.command('unicast')
def clear_pwm_q_uni():
    """Clear persistent WM for persistent queues"""
    command = 'watermarkstat -c -p -t q_shared_uni'
    run_command(command)

@persistent_watermark.command('multicast')
def clear_pwm_q_multi():
    """Clear persistent WM for multicast queues"""
    command = 'watermarkstat -c -p -t q_shared_multi'
    run_command(command)

@queue.command('threshold')
@click.argument('port_name', metavar='<port_name>', required=False)
@click.argument('queue_index', metavar='<queue_index>', required=False, type=int)
@click.argument('queue_type', required=False, type=click.Choice(['unicast', 'multicast']))
@click.pass_context
def threshold(ctx, port_name, queue_index, queue_type):
    """ Clear queue threshold for a queue on a port """
    # If no params are provided, clear all priority-group entries.
    config_db = ConfigDBConnector()
    config_db.connect()

    all = False

    if port_name is None and queue_index is None and queue_type is None:
        # clear all entries.
        key = 'queue'
        all = True
    elif port_name is None or queue_index is None or queue_type is None:
        ctx.fail("port_name, queue_index and queue_type are mandatory parameters.")
    else:
        if queue_index not in range(0, 8):
            ctx.fail("queue index must be in range 0-7")
        if interface_name_is_valid(port_name) is False:
            ctx.fail("Interface name is invalid!!")
        key = 'queue' + '|' + queue_type + '|' + port_name + '|' + str(queue_index)

    if all is True:
        entry_table = config_db.get_keys('THRESHOLD_TABLE')
        # Clear data for all keys
        for k in natsorted(entry_table):
            if k[0] == 'queue':
                config_db.set_entry('THRESHOLD_TABLE', k, None)
    else:
        entry = config_db.get_entry('THRESHOLD_TABLE', key)
        if entry:
            config_db.set_entry('THRESHOLD_TABLE', key, None)


#
# 'arp' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def arp(ipaddress):
    """Clear IP ARP table"""
    if ipaddress is not None:
        command = 'sudo ip -4 neigh show {}'.format(ipaddress)
        (out, err) = run_command(command, return_output=True)
        if not err and 'dev' in out:
            outputList = out.split()
            dev = outputList[outputList.index('dev') + 1]
            command = 'sudo ip -4 neigh del {} dev {}'.format(ipaddress, dev)
        else:
            click.echo("Neighbor {} not found".format(ipaddress))
            return
    else:
        command = "sudo ip -4 -s -s neigh flush all"

    run_command(command)

#
# 'ndp' command ####
#

@click.command()
@click.argument('ipaddress', required=False)
def ndp(ipaddress):
    """Clear IPv6 NDP table"""
    if ipaddress is not None:
        command = 'sudo ip -6 neigh show {}'.format(ipaddress)
        (out, err) = run_command(command, return_output=True)
        if not err and 'dev' in out:
            outputList = out.split()
            dev = outputList[outputList.index('dev') + 1]
            command = 'sudo ip -6 neigh del {} dev {}'.format(ipaddress, dev)
        else:
            click.echo("Neighbor {} not found".format(ipaddress))
            return
    else:
        command = 'sudo ip -6 -s -s neigh flush all'

    run_command(command)

# Add 'arp' command to both the root 'cli' group and the 'ip' subgroup
cli.add_command(arp)
cli.add_command(ndp)
ip.add_command(arp)
ip.add_command(ndp)

#
# 'fdb' command ####
#
@cli.group()
def fdb():
    """Clear FDB table"""
    pass

@fdb.command('all')
def clear_all_fdb():
    """Clear All FDB entries"""
    command = 'fdbclear'
    run_command(command)

# 'sonic-clear fdb port' and 'sonic-clear fdb vlan' will be added later
'''
@fdb.command('port')
@click.argument('portid', required=True)
def clear_port_fdb(portid):
    """Clear FDB entries learned from one port"""
    command = 'fdbclear' + ' -p ' + portid
    run_command(command)

@fdb.command('vlan')
@click.argument('vlanid', required=True)
def clear_vlan_fdb(vlanid):
    """Clear FDB entries learned in one VLAN"""
    command = 'fdbclear' + ' -v ' + vlanid
    run_command(command)
'''

#
# 'line' command
#
@cli.command('line')
@click.argument('linenum')
def line(linenum):
    """Clear preexisting connection to line"""
    cmd = "consutil clear " + str(linenum)
    run_command(cmd)


@cli.group('threshold')
def threshold():
    """Clear threshold breach entries"""
    pass

@threshold.command()
@click.argument('id', type=int, required=False)
def breach(id):
    """Clear threshold breach entries all | event-id"""
    if id is not None:
        cmd = "thresholdbreach -c -cnt {}".format(id)
    else:
        cmd = 'thresholdbreach -c'
    run_command(cmd)

#
# 'nat' group ("clear nat ...")
#

@cli.group(cls=AliasedGroup, default_if_no_args=False)
def nat():
    """Clear the nat info"""
    pass

# 'statistics' subcommand ("clear nat statistics")
@nat.command()
def statistics():
    """ Clear all NAT statistics """

    cmd = "natclear -s"
    run_command(cmd)

# 'translations' subcommand ("clear nat translations")
@nat.command()
def translations():
    """ Clear all NAT translations """

    cmd = "natclear -t"
    run_command(cmd)

if __name__ == '__main__':
    cli()
