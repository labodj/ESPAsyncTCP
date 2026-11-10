"""Execute production TCP methods against a controllable lwIP peer."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def method(signature):
    source = (ROOT / "src/ESPAsyncTCP.cpp").read_text()
    start = source.index(signature)
    return source[start:source.index("\n}", start) + 2]


FIXTURE = r"""
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <memory>
#include <string>
#define ASYNC_TCP_SSL_ENABLED 0
#define ASYNC_TCP_DEBUG(...) do {} while (0)
using err_t=int;
constexpr err_t ERR_OK=0,ERR_MEM=-1,ERR_RTE=-4,ERR_ABRT=-13;
uint32_t clockMs=0;
uint32_t millis(){return clockMs;}
struct tcp_pcb{unsigned writes=0,outputs=0;std::string queued;};
err_t outputError=ERR_OK,writeError=ERR_OK;
err_t tcp_output(tcp_pcb *pcb){assert(pcb);++pcb->outputs;return outputError;}
err_t tcp_write(tcp_pcb *pcb,const void *data,size_t length,uint8_t){
  if(writeError!=ERR_OK)return writeError;
  ++pcb->writes;pcb->queued.append(static_cast<const char*>(data),length);return ERR_OK;
}
struct ACErrorTracker{
  bool present=true;err_t error=0;
  void setCloseError(err_t value){error=value;}
  bool hasClient()const{return present;}
};
struct AsyncClient{
  tcp_pcb pcb;tcp_pcb *_pcb=&pcb;
  std::shared_ptr<ACErrorTracker> tracker=std::make_shared<ACErrorTracker>();
  bool _pcb_busy=false,_tx_output_pending=false,_close_pcb=false,closed=false;
  uint32_t _pcb_sent_at=0,_ack_timeout=5000,_rx_since_timeout=0,_rx_last_packet=0;
  size_t _tx_unacked_len=0,capacity=4;
  std::function<void(void*,AsyncClient*,uint32_t)>_timeout_cb;
  std::function<void(void*,AsyncClient*)>_poll_cb;
  void *_timeout_cb_arg=nullptr,*_poll_cb_arg=nullptr;
  ~AsyncClient(){tracker->present=false;}
  void setCloseError(err_t value){tracker->error=value;}
  size_t space()const{return capacity-_tx_unacked_len;}
  void _close(){closed=true;}
  void abort();bool send();bool canSend();
  size_t add(const char*,size_t,uint8_t);
  size_t write(const char*,size_t,uint8_t);
  void _poll(std::shared_ptr<ACErrorTracker>&,tcp_pcb*);
};
AsyncClient *active=nullptr;
unsigned abortCalls=0;
bool detached=false,marked=false;
void tcp_abort(tcp_pcb *pcb){
  assert(pcb);++abortCalls;
  detached=active->_pcb==nullptr;marked=active->tracker->error==ERR_ABRT;
  delete active;active=nullptr;
}
"""
SOURCE = FIXTURE + "\n".join(method(signature) for signature in (
    "void AsyncClient::abort()",
    "size_t AsyncClient::add(const char* data, size_t size, uint8_t apiflags)",
    "size_t AsyncClient::write(const char* data, size_t size, uint8_t apiflags)",
    "bool AsyncClient::send()",
    "bool AsyncClient::canSend()",
    "void AsyncClient::_poll(std::shared_ptr<ACErrorTracker>& errorTracker, tcp_pcb* pcb)",
)) + r"""
int main(int argc,char **argv){
  assert(argc==2);const std::string scenario=argv[1];
  if(scenario=="abort"){
    active=new AsyncClient;auto tracker=active->tracker;active->abort();
    assert(!active&&abortCalls==1&&detached&&marked&&!tracker->present);
    AsyncClient empty;empty._pcb=nullptr;empty.abort();assert(abortCalls==1);
    return 0;
  }
  AsyncClient client;auto tracker=client.tracker;
  if(scenario=="empty"){
    for(unsigned i=0;i<10;++i){assert(client.send());assert(client.canSend());}
    assert(!client._tx_output_pending);return 0;
  }
  if(scenario=="write_mem"||scenario=="write_route"){
    outputError=scenario=="write_mem"?ERR_MEM:ERR_RTE;
    assert(client.write("data",4,1)==4);
    assert(client.pcb.queued=="data"&&client.pcb.writes==1&&client._tx_output_pending);
    assert(!client.canSend());
    outputError=ERR_OK;clockMs=10;client._poll(tracker,&client.pcb);
    assert(client.pcb.outputs==2&&!client._tx_output_pending&&client._pcb_busy);
    assert(client.pcb.writes==1&&client.pcb.queued=="data");return 0;
  }
  if(scenario=="empty_retry"){
    outputError=ERR_MEM;assert(client.send());assert(client._tx_output_pending);
    outputError=ERR_OK;client._poll(tracker,&client.pcb);
    assert(client.pcb.outputs==2&&client.canSend()&&!client._tx_output_pending);return 0;
  }
  if(scenario=="write_failure"){
    writeError=ERR_MEM;assert(client.write("data",4,1)==0);
    assert(client.pcb.queued.empty()&&client.pcb.outputs==0&&!client._tx_output_pending);
    writeError=ERR_OK;assert(client.write("data",4,1)==4);assert(client.pcb.queued=="data");return 0;
  }
  assert(scenario=="timeout_mem"||scenario=="timeout_route"||scenario=="timeout_rollover");
  outputError=scenario=="timeout_route"?ERR_RTE:ERR_MEM;
  const uint32_t start=scenario=="timeout_rollover"?0xfffffff0U:100U;
  clockMs=start;assert(client.add("data",4,1)==4);client.send();
  unsigned timeouts=0;client._timeout_cb=[&](void*,AsyncClient*,uint32_t elapsed){assert(elapsed==5000);++timeouts;};
  clockMs=start+4999U;client._poll(tracker,&client.pcb);
  assert(timeouts==0&&client._pcb_sent_at==start&&client._tx_output_pending);
  clockMs=start+5000U;client._poll(tracker,&client.pcb);
  assert(timeouts==1&&client.pcb.outputs==3&&client.pcb.writes==1);
}
"""


class TcpTests(unittest.TestCase):
    def run_cases(self, cases):
        with tempfile.TemporaryDirectory(prefix="espasynctcp-test-") as directory:
            cpp=Path(directory)/"tcp.cpp"
            cpp.write_text(SOURCE)
            binary=Path(directory)/"tcp"
            subprocess.run([os.environ.get("CXX","g++"),"-std=c++17","-O1","-g",
                            "-fsanitize=address,undefined","-fno-sanitize-recover=all",
                            "-fno-omit-frame-pointer",str(cpp),"-o",str(binary)],check=True)
            for case in cases:
                with self.subTest(case=case):
                    result=subprocess.run([str(binary),case],capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_abort_callback_can_destroy_client(self):
        self.run_cases(("abort",))

    def test_queued_output_and_timeout(self):
        self.run_cases(("empty","write_mem","write_route","empty_retry","write_failure",
                        "timeout_mem","timeout_route","timeout_rollover"))


if __name__=="__main__":
    unittest.main()
