import React from 'react'
import {Link, withRouter} from 'react-router-dom'

import {MenuSurface, MenuSurfaceAnchor} from '@rmwc/menu';

import Button from '../SkaleButton/SkaleButton';
import {Icon} from "rmwc/Icon";

const REQUEST_INTERVAL = 3000;
const REQUEST_URL = '/user-info';
const LOGOUT_URL = '/logout';
const LOGIN_URL = '/login';
const SING_UP_URL = '/create-user';

class SkaleAccount extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      loaded: false,
      accountInfo: undefined
    };

    this.logout = this.logout.bind(this);
    this.getUserInfo = this.getUserInfo.bind(this);
  }

  async componentDidMount() {
    this.initGetUserInfoTimer();
  }

  initGetUserInfoTimer() {
    this.getUserInfo();
    this.setState({
      timer: setInterval(() => {
        this.getUserInfo()
      }, REQUEST_INTERVAL),
    });
  }

  componentWillUnmount() {
    clearInterval(this.state.timer);
  }

  getUserInfo() {
    let self = this;
    fetch(REQUEST_URL, {
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
      if (data.data && data.data.no_users){
        self.props.history.push(SING_UP_URL);
      }else{
        self.setState({accountInfo: data.data})
      }
    })
  }

  logout() {
    let self = this;
    fetch(LOGOUT_URL, {
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
      //self.props.setMenuVisibility(true);
      self.setState({genericMenuIsOpen: false});
      self.props.history.push(LOGIN_URL);
    })
  }


  render() {

    let content;

    if (this.state.accountInfo) {
      content = (
        <div>
          <div className='bord-bott marg-bott-10'>
            <h6 className='fs-4 fw-4 g-6 marg-bott-sm'>
              Current user
            </h6>
            <h4 className='no-marg padd-bott-15 fw-6 fs-10'>
              {this.state.accountInfo.username}
            </h4>
          </div>

          <Button size="lg" color='transparent' style={{width: '100%'}} onClick={this.logout}>
            Logout
            <Icon strategy="ligature"
                  className="white-icon sm-icon marg-left-10">arrow_forward</Icon>
          </Button>


        </div>
      )
    } else {
      content = (
        <div>
          <h6 className='text-center bord-bott padd-bott-md'>
            You're not logged in.
          </h6>

          <Link to='/login' className='undec' onClick={evt => this.setState({genericMenuIsOpen: false})}>
            <Button size="lg" color='transparent' style={{width: '100%'}}>
              Login
              <Icon strategy="ligature"
                    className="white-icon sm-icon marg-left-10">arrow_forward</Icon>
            </Button>
          </Link>
        </div>
      )
    }

    return (
      <div>
        <MenuSurfaceAnchor>
          <MenuSurface
            anchorCorner='bottomLeft'
            open={this.state.genericMenuIsOpen}
            onClose={evt => this.setState({genericMenuIsOpen: false})}
          >
            <div style={{padding: '20px 20px 10px 20px', minWidth: '250px'}}>
              {content}
            </div>
          </MenuSurface>
          <div onClick={evt => this.setState({'genericMenuIsOpen': !this.state.genericMenuIsOpen})}>
            {this.props.children}
          </div>
        </MenuSurfaceAnchor>
      </div>
    );
  }
}

export default withRouter(SkaleAccount);