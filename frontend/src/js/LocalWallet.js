import React from 'react'
import {CopyToClipboard} from 'react-copy-to-clipboard';

import Web3 from 'web3';
const web3 = new Web3(Web3.givenProvider);

import Button from './SkaleButton/SkaleButton';
import {Icon} from 'rmwc/Icon';
import {Snackbar} from 'rmwc/Snackbar';
import {Popover, PopoverHeader, PopoverBody} from 'reactstrap';
import {LinearProgress} from "rmwc/LinearProgress";
import {Link, withRouter} from 'react-router-dom';

const DEPOSIT_AMOUNT_SKL = 100;
const DEPOSIT_AMOUNT_ETH = 0.2;

// todo: move it to helper
const ERROR_PATH = '/error';
const LOGIN_PATH = '/login';
function constructErrorPath(error) {
  return ERROR_PATH + '?error=' + error;
}


class LocalWallet extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      popoverOpen: false,
      loading: true
    };
    this.connected = this.connected.bind(this);
    this.installNode = this.installNode.bind(this);
    this.togglePopover = this.togglePopover.bind(this);
  }

  async componentDidMount() {
      this.initBalanceChecker();
    //let skale = this.props.skale;
   // if (skale) {
    //  this.connected(skale);
    //}
  }

  componentWillUnmount() {
    clearInterval(this.state.timer);
  }

  componentWillReceiveProps() {
    if (!this.state.libInit && this.props.skale) {
      this.setState({libInit: true});
      this.initBalanceChecker();
    }
  }

  loadWallet() {
    let self = this;
    fetch('/load-wallet', {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      //body: JSON.stringify(nodeConfig)
    }).then(function (response) {
      return response.json()
    }, function (error) {
      console.error(error.message);
    }).then(function (data) {


      if (data.errors) {
        //let errorPath = constructErrorPath(data.errors[0].msg);
        self.props.history.push(LOGIN_PATH);
      }

      let accountSkaleBalance = data.data.skale_balance;
      let accountEthBalance = data.data.eth_balance;

      self.setState({
        address: data.data.address,
        connected: true,
        loading: false,
        skl: parseFloat(accountSkaleBalance).toFixed(3),
        eth: parseFloat(accountEthBalance).toFixed(3)
      })
      //self.props.history.push('/local-wallet/' + data.address);
    })
  }


  connected(skale) {
    this.skale = skale;
    this.setState({connected: true});
    this.initBalanceChecker();
  }

  initBalanceChecker() {
    this.loadWallet();
    this.setState({
      timer: setInterval(() => {
        this.loadWallet()
      }, 3000),
    });
  }

  isEnoughDeposit() {
    return (this.state.skl >= DEPOSIT_AMOUNT_SKL && this.state.eth >= DEPOSIT_AMOUNT_ETH)
  }

  installNode() {
    this.props.history.push('/create-node');
  }

  togglePopover() {
    this.setState({
      popoverOpen: !this.state.popoverOpen
    });
    let self = this;
    setTimeout(function () {
      self.setState({
        popoverOpen: !self.state.popoverOpen
      });
    }, 1000);
  }

  render() {
    return (
      <div className="marg-30">
        <div className="fl-cont fl-center-vert content-center">
          <div className="fl-col fl-grow"></div>
          <div className="fl-col text-center">

            <div className={this.state.loading ? '' : 'hidden'}>
              <h4 className="padd-bott-10">Loading wallet info</h4>
              <div style={{width: "340px", margin: "auto"}}>
                <LinearProgress determinate={false}></LinearProgress>
              </div>
            </div>

            <div className={this.state.loading ? 'hidden' : ''}>
              <h6 className="marg-bott-30 fw-4 g-4">
                This is your local node wallet address
              </h6>

              <div className="fl-cont fl-center-vert local-wallet-box"
                   style={{padding: '15px 45px', borderRadius: '10px'}}>
                <div className="fl-col padd-ri-md">
                  <h1 className="no-marg">
                    {this.state.address}
                  </h1>
                </div>
                <div className="fl-col padd-left-md padd-ri-10 md-icon hand-cursor">
                  <CopyToClipboard text={this.state.address}>
                    <Icon strategy="ligature" className="accent-icon" id="Popover1"
                          onClick={this.togglePopover}>file_copy</Icon>
                  </CopyToClipboard>
                </div>
              </div>


              <div className="padd-top-30 padd-bott-30">
                <h6 className="marg-bott-30 fw-6 g-6">
                  You need to transfer {DEPOSIT_AMOUNT_SKL} SKALE and {DEPOSIT_AMOUNT_ETH} ETH to this
                  account to create a node.
                </h6>
                <h6 className="marg-bott-md padd-top-md fw-4 g-4">
                  Account balance
                </h6>
                <h2 className="">
                  {this.state.skl} SKALE
                </h2>
                <h2 className="">
                  {this.state.eth} ETH
                </h2>
              </div>

              <Button size="lg" disabled={!this.isEnoughDeposit()} onClick={this.installNode}>
                Configure node
                <Icon strategy="ligature"
                      className="white-icon sm-icon marg-left-10">arrow_forward</Icon>
              </Button>
            </div>
          </div>
          <div className="fl-col fl-grow"></div>
        </div>

        <Popover placement="bottom" isOpen={this.state.popoverOpen} target="Popover1"
                 toggle={this.togglePopover}>
          <PopoverHeader>Address copied to clipboard</PopoverHeader>
        </Popover>

      </div>
    )
  }
}

export default withRouter(LocalWallet, { withRef: true });
