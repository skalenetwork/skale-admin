import React from 'react'
import ProgressBar from "./shared_components/ProgressBar";
import PageTitle from "./shared_components/PageTitle";
import CardTitle from "./shared_components/CardTitle";
import {Link, withRouter} from 'react-router-dom';

import Web3 from 'web3';
const web3 = new Web3(Web3.givenProvider);

// todo: move it to helper
const ERROR_PATH = '/error';
const LOGIN_PATH = '/login';
function constructErrorPath(error) {
  return ERROR_PATH + '?error=' + error;
}

class About extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      loaded: false,
      localWallet: {}
    };
  }

  componentDidMount() {
    this.initAboutChecker();
  }

  componentWillUnmount() {
    this.destroyAboutChecker();
  }

  destroyAboutChecker() {
    clearInterval(this.state.aboutTimer)
  }

  initAboutChecker() {
    this.checkAbout();
    this.setState({
      aboutTimer: setInterval(() => {
        this.checkAbout()
      }, 6000),
    });
  }

  checkAbout() {
    const url = '/about-node';
    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (resData) {
        let data = resData.data;

        if (data.errors){
          //let errorPath = constructErrorPath(data.errors[0].msg);
          self.props.history.push(LOGIN_PATH);
        }

        if (data.local_wallet.address) {
          data.local_wallet.eth_balance = web3.utils.fromWei(data.local_wallet.eth_balance);
          data.local_wallet.skale_balance = web3.utils.fromWei(data.local_wallet.skale_balance);
        }

        self.setState({
          libraries: data.libraries,
          contracts: data.contracts,
          network: data.network,
          localWallet: data.local_wallet,
          loaded: true
        });
      })
      .catch(function (error) {
        console.log(error);
      });
  }


  render() {
    let content = (this.state.loaded ?
        <div>
          <div className="padd-left-sm">
            <PageTitle title='About'/>
            <div className="new-card">
              <CardTitle icon="extension" text="Libraries" color="lite-green" className="padd-bott-md"/>

              <div className='padd-left-md'>
                <table>
                  <tr>
                    <td className='padd-ri-md'><h6>Python</h6></td>
                    <td><h6 className='g-4'>{this.state.libraries.python}</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>Javascript</h6></td>
                    <td><h6 className='g-4'>{this.state.libraries.javascript}</h6></td>
                  </tr>
                </table>
              </div>


              <CardTitle icon="description" text="Contracts" color="purple"
                         className="padd-top-md padd-bott-md"/>

              <div className='padd-left-md'>
                <table>
                  <tr>
                    <td className='padd-ri-md'><h6>Custom contracts</h6></td>
                    <td><h6
                      className='g-4'>{this.state.contracts.custom_contracts ? 'Yes' : 'No'}</h6>
                    </td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>Manager</h6></td>
                    <td><h6 className='g-4'>{this.state.contracts.manager}</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>Token</h6></td>
                    <td><h6 className='g-4'>{this.state.contracts.token}</h6></td>
                  </tr>
                </table>
              </div>

              <CardTitle icon="wifi_tethering" text="Network" color="blue"
                         className="padd-top-md padd-bott-md"/>

              <div className='padd-left-md'>
                <table>
                  <tr>
                    <td className='padd-ri-md'><h6>IP</h6></td>
                    <td><h6 className='g-4'>{this.state.network.ip}</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>Port</h6></td>
                    <td><h6 className='g-4'>{this.state.network.port}</h6></td>
                  </tr>
                </table>
              </div>

              <CardTitle icon="account_balance_wallet" text="Local wallet" color="pink"
                         className="padd-top-md padd-bott-md"/>

              <div className='padd-left-md'>


                {
                  !this.state.localWallet.address ? (<h6 className='g-4'>Local wallet not created</h6>) :
                    (<table>
                      <tr>
                        <td className='padd-ri-md'><h6>Address</h6></td>
                        <td><h6 className='g-4'>{this.state.localWallet.address}</h6></td>
                      </tr>
                      <tr>
                        <td className='padd-ri-md'><h6>ETH balance</h6></td>
                        <td><h6 className='g-4'>{this.state.localWallet.eth_balance}</h6></td>
                      </tr>
                      <tr>
                        <td className='padd-ri-md'><h6>SKL balance</h6></td>
                        <td><h6 className='g-4'>{this.state.localWallet.skale_balance}</h6></td>
                      </tr>
                    </table>)

                }

              </div>

              <CardTitle icon="dns" text="Containers" color="orange"
                         className="padd-top-md padd-bott-md"/>

              <div className='padd-left-md'>
                <table>
                  <tr>
                    <td className='padd-ri-md'><h6>Admin</h6></td>
                    <td><h6 className='g-4'>Latest</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>MySQL</h6></td>
                    <td><h6 className='g-4'>Latest</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>Bounty</h6></td>
                    <td><h6 className='g-4'>Latest</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>SLA</h6></td>
                    <td><h6 className='g-4'>Latest</h6></td>
                  </tr>
                  <tr>
                    <td className='padd-ri-md'><h6>Events</h6></td>
                    <td><h6 className='g-4'>Latest</h6></td>
                  </tr>

                </table>
              </div>

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

export default withRouter(About);
