import React from 'react'
import {Link, withRouter} from 'react-router-dom';

import {Input, Container, Tooltip} from 'reactstrap';
import Button from './SkaleButton/SkaleButton';

import PageTitle from "./shared_components/PageTitle";
import CardTitle from "./shared_components/CardTitle";
import SkInput from "./shared_components/SkInput";
import Flash from "./shared_components/Flash";
import {Icon} from "rmwc/Icon";
import {LinearProgress} from "rmwc/LinearProgress";

const DASHBOARD_URL = '/';

class Login extends React.Component {

  constructor(props) {
    super(props);

    this.state = {
      username: '',
      password: '',
    };
    this.login = this.login.bind(this);

    this.checkUsername = this.checkUsername.bind(this);
    this.checkPassword = this.checkPassword.bind(this);

    this.setUsername = this.setUsername.bind(this);
    this.setPassword = this.setPassword.bind(this);
  }

  login() {
    let self = this;
    this.setState({flashMessages: null, flashType: null});

    let user = {
      username: this.state.username,
      password: this.state.password
    };

    fetch('/login', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(user)
    }).then((response) => response.json()).then((data) => {

      if (data.errors) {
        this.setState({flashMessages: data.errors, flashType: 'error'});
      }
      else {
        self.props.setMenuVisibility(false);
        self.props.history.push(DASHBOARD_URL);
      }
    })
      .catch(error => {
        this.displayFormError(error);
        return error;
      });
  }

  displayFormError(error) {
    // todo!
  }

  async checkUsername(username) {
    // todo: check!
    /*if (skaleNodeName === '') {
      this.setState({validatingName: false, validNodeName: false, nodeNameError: 'Node name couldn\'t be empty'});
      return
    }
    this.setState({validatingName: true});
    let response = await fetch(`/check-node-name?nodeName=${skaleNodeName}`);
    let valid = await response.json();
    let nodeNameError = valid ? undefined : 'Name is already taken';
    this.setState({validatingName: false, validNodeName: valid, nodeNameError: nodeNameError});*/
  }

  setUsername(value) {
    this.setState({username: value});
  }

  async checkPassword(password) {
    // todo: check!
  }

  setPassword(value) {
    this.setState({password: value});
  }

  render() {
    return (
      <div className="marg-30">
        <div className="fl-cont fl-center-vert content-center">
          <div className="fl-col fl-grow"></div>
          <div className="fl-col fl-grow text-center">
            <div className={this.state.loading ? 'hidden' : ''}>
              <h2 className=''>
                Welcome to SKALE Node UI
              </h2>
              <h6 className="marg-bott-big fw-4 g-4">
                Please login to continue
              </h6>


              <div className="form-wrap" style={{maxWidth: "450px", textAlign: 'left', margin: '0 auto', paddingBottom: '50px'}}>

                <Flash className='marg-bott-md' messages={this.state.flashMessages} type={this.state.flashType}/>

                <SkInput
                  title='Username'
                  placeholder='Enter username'
                  error={this.state.usernameError}
                  disabled={this.state.validatingUsername}
                  onBlur={this.checkUsername}
                  valid={this.state.validUsername}
                  updateVariable={this.setUsername}
                  value={this.state.username}
                />

                <br/>

                <SkInput
                  title='Password'
                  placeholder='Enter password'
                  error={this.state.passwordError}
                  disabled={this.state.validatingPassword}
                  onBlur={this.checkPassword}
                  valid={this.state.validPassword}
                  updateVariable={this.setPassword}
                  value={this.state.password}
                  type='password'
                />

              </div>

              <Button size="lg" onClick={this.login}>
                Sign in
                <Icon strategy="ligature"
                      className="white-icon sm-icon marg-left-10">arrow_forward</Icon>
              </Button>

              <div className='marg-top-big'>
                <h6 className='fs-2 g-4'>
                  Don't have an account?
                  <Link to='/create-user' className='marg-left-sm'>
                    Create one
                  </Link>
                </h6>
              </div>

            </div>
          </div>
          <div className="fl-col fl-grow"></div>
        </div>
      </div>
    );
  }
}

export default withRouter(Login);