import React from 'react'
import {LinearProgress} from 'rmwc/LinearProgress';
import {Link, withRouter} from 'react-router-dom';

class Error extends React.Component {
  render() {

    let query = new URLSearchParams(this.props.location.search);
    let error = query.get('error');

    return (
      <div>
        <div className={"cont fl-cont fl-center web3connection"} style={{textAlign: "center", height: "100vh"}}>
          <div className="fl-wrap fl-grow">
            <h2>Error occured</h2>
            <h6 className="padd-bott-md lite-gr-col" style={{lineHeight: "1.6"}}>
              {error}
            </h6>
          </div>
        </div>
      </div>
    );
  }
}

export default withRouter(Error);