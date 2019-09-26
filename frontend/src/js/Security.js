import React from 'react'
import ProgressBar from "./shared_components/ProgressBar";
import PageTitle from "./shared_components/PageTitle";
import {Link, withRouter} from 'react-router-dom';
import Button from "./SkaleButton/SkaleButton";

import {LinearProgress} from 'rmwc/LinearProgress';


import {Snackbar} from '@rmwc/snackbar';

import CertificatePreview from "./CertificatePreview";


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
      certificates: []
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
    this.getCertificates();
    this.setState({
      schainsTimer: setInterval(() => {
        this.getCertificates()
      }, 6000),
    });
  }

  getCertificates() {
    const url = '/certificates-info';
    let self = this;
    fetch(url)
      .then((resp) => resp.json())
      .then(function (data) {

        if (data.errors) {
          //let errorPath = constructErrorPath(data.errors[0].msg);
          self.props.history.push(LOGIN_PATH);
        }

        self.setState({
          certificates: data.data,
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

    const certificates = this.state.certificates.map((item, i) =>
      <div key={i}>
        <CertificatePreview darkMode={this.props.darkMode} item={item}/>
      </div>
    );

    let content = (this.state.loaded ?
        <div>
          <div className="padd-left-sm">
            <div className='fl-cont'>
              <div className='fl-col fl-grow'>
                <PageTitle title='Security'/>

              </div>
              <div className='fl-col'>
                <div style={{marginTop: '-5px'}}>
                  <Link className="undec" to='/add-certificate'>
                    <Button size="md">
                      Upload certificate
                    </Button>
                  </Link>
                </div>
              </div>
            </div>


            <div className="new-card">

              <h5 className="marg-top-sm padd-bott-sm fw-6 fs-6">
                SSL certificates
              </h5>
              {certificates.length === 0 ?
                <h6 className='no-marg fs-2 g-4'>No SSL certificates added</h6> : certificates}
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
