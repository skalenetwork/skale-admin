import React from 'react';
import {Switch, Route} from 'react-router-dom'

import CreateNode from './CreateNode';
import Node from './Node';
import SChainsPage from './SChainsPage';
import Security from './Security';
import SlaBounty from './SlaBounty';
import UploadCertificate from './UploadCertificate';
import InstallingNode from './InstallingNode';
import CreateLocalWallet from './CreateLocalWallet';
import LocalWallet from './LocalWallet';
import About from './About';
import CreateUser from './CreateUser';
import Login from './Login';
import Logs from './Logs';
import Error from './Error';

import Sidebar from './shared_components/Sidebar';

import Web3Connector from './Web3Connector';
import Web3Connection from './Web3Connection';

const skale = require('@skale-labs/skale-api');

const key = 'dark_mode';

const _ = require('lodash');


export default class App extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      web3Connector: {},
      avatarData: '',
      darkMode: true,

    };
    this.setMenuVisibility = this.setMenuVisibility.bind(this);
    this.updateWeb3Connector = this.updateWeb3Connector.bind(this);
    this.setDarkMode = this.setDarkMode.bind(this);

    //this.localWalletComponent = React.createRef();
  }

  componentWillMount() {
    let lsDarkMode = localStorage.getItem(key);
    let darkMode = (lsDarkMode === null || lsDarkMode === 'true');
    this.setState({darkMode: darkMode});
  }

  async getRPCcredentials() {
    const url = '/get-rpc-credentials';
    let response = await fetch(url);
    return await response.json();
  }

  async updateWeb3Connector(web3Connector) {
    this.setState({web3Connector: web3Connector});
    if (web3Connector) {
      let rpcCredentials = await this.getRPCcredentials();
      await skale.initBothProviders(rpcCredentials.ip, rpcCredentials.port, web3Connector.provider, rpcCredentials.contracts_data);
      this.setState({libInit: true, skale: skale, rpcCredentials: rpcCredentials});
      //if (this.localWalletComponent.current) {
      //  this.localWalletComponent.current.connected(skale);
      //}
    }
  }

  setMenuVisibility(hidden) {
    this.setState({hideMenu: hidden});
  }

  async setDarkMode(darkMode) {
    await this.setState({darkMode: darkMode});
    localStorage.setItem(key, this.state.darkMode);
  }

  render() {
/*    let web3Connector = this.state.web3Connector;
    let content;
    if (!web3Connector.provider) {
      content = <Web3Connection darkMode={this.state.darkMode}/>;
    }
    else {*/
      let content = (
        <div>
          {/*<Header avatarData={this.state.avatarData}/>*/}
          <div className={"fl-cont " + (this.state.darkMode ? 'dark-mode' : '')}>
            <div className="fl-wrap">
              <Sidebar persistentOpen="false" hideMenu={this.state.hideMenu}
                       darkMode={this.state.darkMode} setDarkMode={this.setDarkMode}/>
            </div>
            <div className="fl-wrap fl-grow main-content">
              <div className="skale-page-content">
                <Switch>
                  <Route exact path='/'
                         render={(props) => <Node {...props} test="123" darkMode={this.state.darkMode}/>}/>
                  <Route exact path='/create-user'
                         render={(props) => <CreateUser {...props} darkMode={this.state.darkMode}/>}/>

                   <Route exact path='/logs'
                         render={(props) => <Logs {...props} darkMode={this.state.darkMode}/>}/>

                   <Route exact path='/login'
                         render={(props) => <Login {...props} darkMode={this.state.darkMode} setMenuVisibility={this.setMenuVisibility} />}/>

                  <Route exact path='/error'
                         render={(props) => <Error {...props} darkMode={this.state.darkMode}/>}/>


                  <Route path="/node" render={() => <Node test="123" darkMode={this.state.darkMode}
                                                          setMenuVisibility={this.setMenuVisibility}/>}/>

                  <Route path="/schains" render={() => <SChainsPage test="123" darkMode={this.state.darkMode}
                                                          setMenuVisibility={this.setMenuVisibility}/>}/>

                  <Route path="/security" render={() => <Security darkMode={this.state.darkMode}/>}/>
                  <Route path="/add-certificate" render={() => <UploadCertificate darkMode={this.state.darkMode}/>}/>

                  <Route exact path="/sla-bounty" render={() => <SlaBounty darkMode={this.state.darkMode}/>}/>


                  <Route exact path='/welcome'
                         render={() => <CreateLocalWallet
                           setMenuVisibility={this.setMenuVisibility}/>}/>
                  <Route exact path='/local-wallet'
                         render={(props) => <LocalWallet {...props}
                                                         setMenuVisibility={this.setMenuVisibility}
                                                         //ref={this.localWalletComponent}
                                                         getSkaleLib={this.getSkaleLib}
                                                         skale={this.state.skale}/>}/>


                  <Route exact path='/create-node'
                         render={() => <CreateNode setMenuVisibility={this.setMenuVisibility}/>}/>
                  <Route exact path='/installing-node'
                         render={() => <InstallingNode setMenuVisibility={this.setMenuVisibility}/>}/>
                  <Route exact path='/about' render={() => <About setMenuVisibility={this.setMenuVisibility}/>}/>
                </Switch>
              </div>
            </div>
          </div>
        </div>
      );

    return (
      <div className="App">
        {/*<Web3Connector updateWeb3Connector={this.updateWeb3Connector}/>*/}
        {content}
      </div>
    );
  }
}
