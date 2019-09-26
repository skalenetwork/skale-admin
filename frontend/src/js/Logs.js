import React from 'react'
import ProgressBar from "./shared_components/ProgressBar";
import PageTitle from "./shared_components/PageTitle";
import CardTitle from "./shared_components/CardTitle";
import {Link, withRouter} from 'react-router-dom';
import Button from "./SkaleButton/SkaleButton";

import {LinearProgress} from 'rmwc/LinearProgress';
import {Snackbar} from '@rmwc/snackbar';

import Log from "./Log";

const skale = require('@skale-labs/skale-api');

// todo: move it to helper
const LOGIN_PATH = '/login';

class Logs extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      loaded: false,
      logs: []
    };
  }

  componentDidMount() {
    this.initLogsChecker();
  }

  componentWillUnmount() {
    this.destroyLogsChecker();
  }

  destroyLogsChecker() {
    clearInterval(this.state.logsTimer)
  }

  initLogsChecker() {
    this.getLogs();
    this.setState({
      logsTimer: setInterval(() => {
        this.getLogs()
      }, 6000),
    });
  }

  getLogs() {
    const url = '/logs';
    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (res_data) {

        let data = res_data.data;

        if (res_data.errors) {
          self.props.history.push(LOGIN_PATH);
        }

        self.setState({
          logs: data,
          loaded: true
        });
      })
      .catch(function (error) {
        console.log(error);
      });
  }

  render() {

    if (!this.state.loaded) return (<ProgressBar/>);


    const baseLogs = this.state.logs.base.map((log, i) =>
      <div key={i}>
        <Log darkMode={this.props.darkMode} log={log}/>
      </div>
    );


    let sChainLogs = [];
    for (let [key, value] of Object.entries(this.state.logs.schains)) {

      let logs = value['logs'];
      let ports = value['info']['ports'];

      let sChainLog = logs.map((log, i) =>
        <div key={i}>
          <Log darkMode={this.props.darkMode} log={log}/>
        </div>
      );

      sChainLogs.push((
        <div>

          <div className='fl-cont'>
            <div className='fl-col fl-grow'>
              <h5 className="padd-top-md marg-top-10 padd-bott-sm fw-6 fs-6">
                sChain {key}
              </h5>
            </div>
            <div className='fl-col'>
              <h5 className=" padd-left-10 padd-top-md marg-top-10 padd-bott-sm fw-4 fs-2 g-4">
                (http/ws: {ports['httpRpcPort']}, {ports['wsRpcPort']}; https/wss: {ports['httpsRpcPort']}, {ports['wssRpcPort']})
              </h5>
            </div>
          </div>


          {sChainLog}
        </div>
      ));


      console.log(key, value);


    }


    let content = (this.state.loaded ?
        <div>
          <div className="padd-left-sm">
            <PageTitle title='Logs'/>


            <div className="new-card">
              <h5 className=" marg-top-sm padd-bott-sm fw-6 fs-6">
                Base logs
              </h5>
              {baseLogs}
              {sChainLogs}
            </div>
          </div>
        </div> : undefined
    );

    return (
      <div className="marg-30">
        {this.state.loaded ? content : <ProgressBar/>}
      </div>
    );
  }
}

export default withRouter(Logs);
