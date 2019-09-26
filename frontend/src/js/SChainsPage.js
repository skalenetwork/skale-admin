import React from 'react'
import ProgressBar from "./shared_components/ProgressBar";
import PageTitle from "./shared_components/PageTitle";
import CardTitle from "./shared_components/CardTitle";
import {Link, withRouter} from 'react-router-dom';
import Button from "./SkaleButton/SkaleButton";

import {LinearProgress} from 'rmwc/LinearProgress';


import {Snackbar} from '@rmwc/snackbar';

import SChainPreview from "./SChainPreview";
import SChain from "./SChain";

const skale = require('@skale-labs/skale-api');

// todo: move it to helper
const ERROR_PATH = '/error';
const LOGIN_PATH = '/login';

function constructErrorPath(error) {
  return ERROR_PATH + '?error=' + error;
}

class SChainsPage extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      loaded: false,
      schains: []
    };
    this.createSchain = this.createSchain.bind(this);
  }

  componentDidMount() {
    this.initSchainsChecker();
  }

  componentWillUnmount() {
    this.destroyAboutChecker();
  }

  destroyAboutChecker() {
    clearInterval(this.state.schainsTimer)
  }

  initSchainsChecker() {
    this.getSchains();
    this.setState({
      schainsTimer: setInterval(() => {
        this.getSchains()
      }, 6000),
    });
  }

  getSchains() {
    const url = '/get-owner-schains';
    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (data) {

        if (data.errors) {
          //let errorPath = constructErrorPath(data.errors[0].msg);
          self.props.history.push(LOGIN_PATH);
        }

        self.setState({
          schains: data.data,
          loaded: true
        });
      })
      .catch(function (error) {
        console.log(error);
      });
  }


  createSchain() {

    this.setState({creatingSchain: true});

    let schainConfig = {
      test: '1'
    };
    let self = this;

    fetch('/create-schain', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(schainConfig)
    }).then((resp) => resp.json())
      .then(function (data) {
        self.setState({
          sChainResult: data.res,
          snackbarIsOpen: !self.state.snackbarIsOpen,
          creatingSchain: false
        });
      })
      .catch(function (error) {
        console.log(error);
      });
  }


  render() {

    // SChainPreview

    const schains = this.state.schains.map((schain, i) =>
      <div key={i}>
        <SChainPreview darkMode={this.props.darkMode} schain={schain}/>
        {/*<Container container={container}/>*/}
      </div>
    );

    let content = (this.state.loaded ?
        <div>
          <div className="padd-left-sm">
            <div className='fl-cont'>
              <div className='fl-col fl-grow'>
                <PageTitle title='sChains'/>

              </div>
              <div className='fl-col'>
                <div style={{marginTop: '-5px'}}>
                  <Button size="md" onClick={this.createSchain}>
                    Create test sChain
                  </Button>
                </div>
              </div>
            </div>


            <div className="new-card">
              {schains.length === 0 ? <h6 className='no-marg'>No sChains</h6> : schains}

              {this.state.creatingSchain ? <LinearProgress className="marg-top-md" determinate={false}></LinearProgress> : undefined}

              <Snackbar
                show={this.state.snackbarIsOpen}
                onHide={evt => this.setState({snackbarIsOpen: false})}
                message={"Result: " + this.state.sChainResult}
                actionText="Close"
                //actionHandler={() => alert('Action clicked')}
                timeout={1000}
                dismissesOnAction={false}
              />


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

export default withRouter(SChainsPage);
