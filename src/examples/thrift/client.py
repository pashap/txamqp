#!/usr/bin/env python

# based on the 'calculator' demo in the Thrift source

import sys, os.path
sys.path.insert(0, os.path.join(os.path.abspath(os.path.split(sys.argv[0])[0]), 'gen-py.twisted'))
import tutorial.Calculator
from tutorial.ttypes import *
from thrift.transport import TTwisted, TTransport
from thrift.protocol import TBinaryProtocol

from twisted.internet import reactor, defer
from twisted.internet.protocol import ClientCreator

import txamqp.spec
from txamqp.client import TwistedDelegate
from txamqp.contrib.thrift.transport import TwistedAMQPTransport
from txamqp.contrib.thrift.protocol import ThriftAMQClient

servicesExchange = "services"
responsesExchange = "responses"
calculatorQueue = "calculator_pool"
calculatorKey = "calculator"

def gotPing(_):
    print("Ping received")

def gotAddResults(results):
    print("Got results to add()")
    print(results)

def gotCalculateResults(results):
    print("Got results to calculate()")
    print(results)

def gotCalculateErrors(error):
    error.trap(InvalidOperation)
    print("Got a calculator error")
    print(error.value.why)

def gotTransportError(error):
    error.trap(TTransport.TTransportException)
    print("Got an AMQP unroutable message error:")
    print(error.value.message)

@defer.inlineCallbacks
def prepareClient(client, username, password):
    yield client.authenticate(username, password)

    channel = yield client.channel(1)

    yield channel.channel_open()
    yield channel.exchange_declare(exchange=servicesExchange, type="direct")
    yield channel.exchange_declare(exchange=responsesExchange, type="direct")

    pfactory = TBinaryProtocol.TBinaryProtocolFactory()

    # To trigger an unroutable message error (caught in the above
    # gotTransportError errback), change the routing key (i.e.,
    # calculatorKey) in the following to be something invalid, like
    # calculatorKey + 'xxx'.
    thriftClient = yield client.createThriftClient(responsesExchange,
        servicesExchange, calculatorKey, tutorial.Calculator.Client,
        iprot_factory=pfactory, oprot_factory=pfactory)
    
    defer.returnValue(thriftClient)

def gotClient(client):
    d1 = client.ping().addCallback(gotPing).addErrback(gotTransportError)

    d2 = client.add(1, 2).addCallback(gotAddResults).addErrback(gotTransportError)

    w = Work(num1=2, num2=3, op=Operation.ADD)

    d3 = client.calculate(1, w).addCallbacks(gotCalculateResults,
        gotCalculateErrors).addErrback(gotTransportError)

    w = Work(num1=2, num2=3, op=Operation.SUBTRACT)

    d4 = client.calculate(2, w).addCallbacks(gotCalculateResults,
        gotCalculateErrors).addErrback(gotTransportError)

    w = Work(num1=2, num2=3, op=Operation.MULTIPLY)

    d5 = client.calculate(3, w).addCallbacks(gotCalculateResults,
        gotCalculateErrors).addErrback(gotTransportError)

    w = Work(num1=2, num2=3, op=Operation.DIVIDE)

    d6 = client.calculate(4, w).addCallbacks(gotCalculateResults,
        gotCalculateErrors).addErrback(gotTransportError)

    # This will fire an errback
    w = Work(num1=2, num2=0, op=Operation.DIVIDE)

    d7 = client.calculate(5, w).addCallbacks(gotCalculateResults,
        gotCalculateErrors).addErrback(gotTransportError)

    d8 = client.zip()

    dl = defer.DeferredList([d1, d2, d3, d4, d5, d6, d7, d8])

    dl.addCallback(lambda _: reactor.stop())

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Example Thrift server",
        usage="%(prog)s localhost 5672 / guest guest ../../specs/standard/amqp0-8.stripped.xml"
    )
    parser.add_argument('host')
    parser.add_argument('port', type=int)
    parser.add_argument('vhost')
    parser.add_argument('username')
    parser.add_argument('password')
    parser.add_argument('spec_path')
    args = parser.parse_args()

    spec = txamqp.spec.load(args.spec_path)

    delegate = TwistedDelegate()

    d = ClientCreator(reactor, ThriftAMQClient, delegate, args.vhost,
        spec).connectTCP(args.host, args.port)
    d.addCallback(prepareClient, args.username, args.password).addCallback(gotClient)
    reactor.run()
