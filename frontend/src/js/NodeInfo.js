import React from 'react'
import {Icon} from 'rmwc/Icon';
import {Container, Row, Col} from 'reactstrap';

import PageTitle from "./shared_components/PageTitle";
import {FlexCont, FlexCol} from "./shared_components/Flex";

import Containers from "./Containers";
import SChains from "./SChains";

export default class NodeInfo extends React.Component {
  render() {
    return (
      <div>
        <div className="padd-left-sm">
          <PageTitle
            title={'Node ' + this.props.node.name + ' (' + this.props.node.id + ')' }
            //subtitle="Manage your Skale node: install, review statistics and more."
            //nopadd={true}
          />
        </div>

        <div className="new-card">
          <Row>
            <Col md={{size: 4}}>

              <div className="big-icon fl-center orange-bg">
                <Icon strategy="ligature" className="md-icon"
                      style={{color: 'rgb(218, 144, 26)'}}>settings</Icon>
              </div>

              <div className="padd-top-md">
                <h6 className="g-4 fs-2">
                  Node P2P IP
                </h6>
                <h6 classID="fs-4">
                  {this.props.node.ip}
                </h6>
              </div>


              <div className="padd-top-md">
                <h6 className="g-4 fs-2">
                  Node public IP
                </h6>
                <h6 classID="fs-4">
                  {this.props.node.publicIP}
                </h6>
              </div>

              <div className="padd-top-md">
                <h6 className="g-4 fs-2">
                  Node port
                </h6>
                <h6 classID="fs-4">
                  {this.props.node.port}
                </h6>
              </div>

            </Col>
            <Col md={{size: 4}}>
              <div className="big-icon fl-center blue-bg">
                <Icon strategy="ligature" className="md-icon"
                      style={{color: '#4d7cff'}}>person</Icon>
              </div>

              <div className="padd-top-md">
                <h6 className="g-4 fs-2">
                  Node owner
                </h6>
                <h6 classID="fs-4">
                  {this.props.node.owner}
                </h6>
              </div>


              <div className="padd-top-md">
                <h6 className="g-4 fs-2">
                  Recovery account
                </h6>
                <h6 className="fs-4">
                  -
                </h6>
              </div>
            </Col>
          </Row>
        </div>


        <h5 className="padd-top-30 padd-bott-10">
          Base containers
        </h5>

        <div className="new-card">
          <Containers fetchUrl='/containers-info' darkMode={this.props.darkMode}/>
        </div>


        <h5 className="padd-top-30 padd-bott-10">
          sChains
        </h5>
        <div className="new-card">
          <SChains darkMode={this.props.darkMode}/>
        </div>


       {/* <h5 className="padd-top-30 padd-bott-10">
          Validation
        </h5>
        <div className="new-card">
          todo
        </div>
*/}
      </div>
    )
  }
}